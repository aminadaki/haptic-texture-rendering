import requests
import time
import struct
import struct
import os
import soundfile as sf
import numpy as np
from datetime import datetime



output_directory = r"C:\Users\annam\Desktop\data"
base_url = "http://192.168.1.9"
# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)


def detect_audio_format(raw_data):
    try:
        # Check for 32-bit PCM (signed integer)
        samples_int = struct.unpack('<' + 'i' * (len(raw_data) // 4), raw_data)
        if all(-2147483648 <= sample <= 2147483647 for sample in samples_int):
            print("Audio format detected: 32-bit PCM (signed integer)")
            return 'pcm_32'
    except struct.error:
        pass

    try:
        # Check for 32-bit float
        samples_float = struct.unpack('<' + 'f' * (len(raw_data) // 4), raw_data)
        if all(-1.0 <= sample <= 1.0 for sample in samples_float):
            print("Audio format detected: 32-bit float")
            return 'float_32'
    except struct.error:
        pass

    print("Unable to determine audio format. The data might be corrupted or in an unexpected format.")
    return 'unknown'

def download_recording(unique_id, retries=5, delay=5):
    url = f"{base_url}/download"
    expected_size = 768000
    
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                received_size = int(response.headers.get('X-File-Size', 0))
                common_start_time = int(response.headers.get('X-Common-Start-Time', 0))
                common_end_time = int(response.headers.get('X-Common-End-Time', 0))

                raw_file_path = os.path.join(output_directory, f"recording_{unique_id}.raw")
                with open(raw_file_path, 'wb') as file:
                    file.write(response.content)
                
                print(f"Recording saved to raw audio, size: {received_size} bytes")
                if received_size == expected_size:
                    print("Received size matches expected size.")
                else:
                    print("Warning: Received size does not match expected size!")
                
                audio_format = detect_audio_format(response.content)
                return raw_file_path, audio_format,common_start_time,common_end_time
            else:
                print(f"Failed to download recording: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print(f"Failed to download recording after {retries} attempts.")
    return None, None, None, None

def download_accel_data(unique_id, retries=5, delay=5):
    url = f"{base_url}/download_accel"
    expected_size = 51200
    
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                accel_file_path = os.path.join(output_directory, f"accelerometer_{unique_id}.dat")
    
                with open(accel_file_path, 'wb') as file:
                    file.write(response.content)
                received_size = int(response.headers.get('X-File-Size', 0))
                print(f"Accelerometer data saved to path, size: {received_size} bytes")
                if received_size == expected_size:
                    print("Received size matches expected size.")
                else:
                    print("Warning: Received size does not match expected size!")
                return accel_file_path
            else:
                print(f"Failed to download accelerometer data: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print(f"Failed to download accelerometer data after {retries} attempts.")
    return None, None, None

#create a WAV file from raw audio data with proper 24-bit extraction
def create_wav_file(raw_file_path, unique_id, audio_format):
    if raw_file_path is None or audio_format == 'unknown':
        print("Invalid file path or unknown audio format; cannot convert to WAV.")
        return

    wav_file_path = os.path.join(output_directory, f"recording_{unique_id}.wav")
    print("Converting raw file to 24-bit WAV format...")
    
    try:
        with open(raw_file_path, "rb") as raw_file:
            raw_data = raw_file.read()

        print(f"Read {len(raw_data)} bytes from raw file")

        #Handle the 32-bit PCM data
        if audio_format == 'pcm_32':
            num_samples = len(raw_data) // 4  #4 bytes per 32-bit sample
            samples_32bit = struct.unpack('<' + 'i' * num_samples, raw_data)
            #shift the 32-bit data to extract the significant 24 bits
            samples_24bit = [(sample >> 8) for sample in samples_32bit]  #remove the lower 8 bits
            #convert the 24-bit samples to float32 for WAV file writing (normalize to range [-1, 1])
            max_24bit_value = 2 ** 23  #max value for 24-bit signed PCM
            samples_float32 = np.array(samples_24bit, dtype=np.float32) / max_24bit_value
            # Save the data to a 24-bit PCM WAV file
            sf.write(wav_file_path, samples_float32, 48000, subtype='PCM_24')
        
        elif audio_format == 'float_32':
            #if it's already float 32 format, just save as is
            samples_float32 = struct.unpack('<' + 'f' * (len(raw_data) // 4), raw_data)
            samples_float32 = np.array(samples_float32, dtype=np.float32)
            # Save the data to a WAV file 
            sf.write(wav_file_path, samples_float32, 48000, subtype='PCM_32')

        else:
            print("Unsupported audio format")
            return

        print(f"Conversion to WAV format completed: {wav_file_path}")
    
    except Exception as e:
        print(f"Error during WAV conversion: {e}")

def download_audio_timestamps(unique_id, retries=5, delay=5):
    url = f"{base_url}/download_audio_timestamps"
    
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                timestamps_file_path = os.path.join(output_directory, f"audio_timestamps_{unique_id}.txt")
                raw_data = response.content #raw uint64_t data (binary)
                num_timestamps = len(raw_data) // 8  #8 bytes per uint64_t
                timestamps = struct.unpack(f'<{num_timestamps}Q', raw_data)  #Q is for uint64_t
                with open(timestamps_file_path, 'w') as file:
                    for ts in timestamps:
                        file.write(f"{ts}\n") 
                print(f"Audio timestamps saved to path: {timestamps_file_path}")
                return timestamps_file_path
            else:
                print(f"Failed to download audio timestamps: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print(f"Failed to download audio timestamps after {retries} attempts.")
    return None

def convert_accel_data_to_csv(accel_file_path, unique_id):
    if accel_file_path is None:
        return
    #bounds for X and Y axes (±2g with tolerance)
    lower_bound_xy = -19.62 
    upper_bound_xy = 19.62 
    
    csv_file_path = os.path.join(output_directory, f"accelerometer_{unique_id}.csv")
    print("Converting accelerometer data to CSV format...")
    
    try:
        with open(accel_file_path, "rb") as accel_file:
            accel_data = accel_file.read()
        num_records = len(accel_data) // struct.calcsize('Qfff')
        records = struct.unpack('<' + 'Qfff' * num_records, accel_data)

        with open(csv_file_path, 'w') as csv_file:
            csv_file.write("Timestamp,Accel_X,Accel_Y,Accel_Z\n")
            for i in range(num_records):
                timestamp = records[i*4]   # uint64_t (timestamp)
                accel_x = records[i*4 + 1] # float (accel_x)
                accel_y = records[i*4 + 2] # float (accel_y)
                accel_z = records[i*4 + 3] # float (accel_z)
                
                #check if X and Y axes are within the range 
                if not (lower_bound_xy <= accel_x <= upper_bound_xy):
                    print(f"Warning: Accel_X out of range at timestamp {timestamp}: {accel_x}")
                if not (lower_bound_xy <= accel_y <= upper_bound_xy):
                    print(f"Warning: Accel_Y out of range at timestamp {timestamp}: {accel_y}")
                
                # Write the accelerometer data to the CSV file
                csv_file.write(f"{timestamp},{accel_x},{accel_y},{accel_z}\n")
        
        print(f"Conversion to CSV format completed.")
    except Exception as e:
        print(f"Error during CSV conversion: {e}")

def connect_to_esp32():
    #rtry logic to handle connection issues
    retries = 3
    while retries > 0:
        try:
            response = requests.get(f"{base_url}/prep", timeout=10)
            if response.status_code == 200:
                print("Calibration triggered.")
                return True
            else:
                print(f"Failed to prepare device: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Connection failed: {e}. Retrying...")
            retries -= 1
            time.sleep(2)
    print("Failed to connect to ESP32 after multiple attempts.")
    return False

#retry logic to handle ESP32 reconnection after recording
def reconnect_after_recording(base_url, retries=10, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(f"{base_url}/status", timeout=10)
            if response.status_code == 200:
                print("Reconnected to ESP32 after recording.")
                return True
        except requests.exceptions.RequestException as e:
            print(f"Reconnection attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
    print("Failed to reconnect to ESP32 after multiple attempts.")
    return False

def safe_request(url, retries=5, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}. Retrying in {delay} seconds...")
            time.sleep(delay)
    print(f"Failed to connect to {url} after {retries} attempts.")
    return None

if __name__ == "__main__":
    unique_id = datetime.now().strftime("%Y%m%d%H%M%S")

    #ensure connection and calibration
    if not safe_request(f"{base_url}/prep"):
        exit()

    #poll for calibration completion
    calibration_complete = False
    while not calibration_complete:
        response = safe_request(f"{base_url}/status")
        if response and "Calibration complete." in response.text:
            print("Calibration complete.")
            calibration_complete = True
        else:
            print("Calibration in progress... waiting...")
            time.sleep(2)  

    time.sleep(3)

    #start recording
    response = safe_request(f"{base_url}/start")
    if response:
        print("Recording started")
    else:
        print("Failed to start recording")
        exit()

    #wait for the duration of the recording 
    time.sleep(5)

    #stop recording
    response = safe_request(f"{base_url}/stop")
    if response:
        print("Recording stopped")
    else:
        print("Failed to stop recording")
        exit()

    time.sleep(1)

    #download the recorded data 
    raw_file_path, audio_format,common_start_time,common_end_time  = download_recording(unique_id)
    if raw_file_path:
        create_wav_file(raw_file_path, unique_id, audio_format)

    timestamps_file_path = download_audio_timestamps(unique_id)
    
    accel_file_path = download_accel_data(unique_id)
    if accel_file_path:
        convert_accel_data_to_csv(accel_file_path, unique_id)

      #save the recording start times 
    if common_start_time is not None and common_end_time is not None:
        start_times_file = os.path.join(output_directory, f'common_start_end_times_{unique_id}.txt')
        with open(start_times_file, 'w') as f:
            f.write(f"Common Start Time (microseconds): {common_start_time}\n")
            f.write(f"Common End Time (microseconds): {common_end_time}\n")
        print(f"Start and End times saved to: {start_times_file}")
    else:
        print("Failed to get start or end times correctly.")
