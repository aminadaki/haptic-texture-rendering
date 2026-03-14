import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import soundfile as sf
import pywt
from scipy.signal import butter, wiener, hilbert, correlate,sosfiltfilt, welch
import scipy.signal as signal
from scipy.interpolate import interp1d, UnivariateSpline
import logging
import sys
from scipy.signal import find_peaks


sys.setrecursionlimit(2000)

logging.basicConfig(level=logging.INFO)

def plot_signal(timestamps, signal, title, ylabel,file_name, color='blue', label='Signal'):
    plt.figure(figsize=(10, 4))
    time_sec = (timestamps - timestamps[0]) / 1e6
    plt.plot(time_sec, signal, color=color, label=label)
    plt.title(title)
    plt.xlabel('Time (s)')
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'/mnt/c/Users/annam/Desktop/plots/{file_name}.png')
    plt.close()

def plot_accel_signal(timestamps, accel_data, title, file_name):
    time_sec = (timestamps - timestamps[0]) / 1e6
    plt.figure(figsize=(10, 6))
    #plt.plot(time_sec, accel_data[:, 0], label='Accel X', color='r')
    plt.plot(time_sec, accel_data[:, 1], label='Accel Y', color='g')
    #plt.plot(time_sec, accel_data[:, 2], label='Accel Z', color='b')
    plt.title(title)
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f'/mnt/c/Users/annam/Desktop/plots/{file_name}.png')
    plt.close()

def load_audio(audio_file_path):
    try:
        #read raw binary audio data
        with open(audio_file_path, "rb") as raw_file:
            raw_data = raw_file.read()
        #determine the number of samples
        audio_num_samples = len(raw_data) // 4  # 4 bytes per 32-bit sample
        #unpack 32-bit samples
        samples_32bit = struct.unpack('<' + 'i' * audio_num_samples, raw_data)
        #convert to 24-bit by discarding the least significant byte
        samples_24bit = np.array([(sample >> 8) for sample in samples_32bit], dtype=np.int32)
        #normalize to floating point
        max_24bit_value = 2 ** 23
        audio_data = samples_24bit.astype(np.float32) / max_24bit_value
        logging.info(f"Loaded audio data from {audio_file_path}")
        return audio_data
    except Exception as e:
        logging.error(f"Error loading audio file: {e}")
        return None

def load_audio_timestamps(audio_timestamps_file):
    try:
        audio_timestamps = np.loadtxt(audio_timestamps_file, dtype=np.int64)
        logging.info(f"Loaded audio timestamps from {audio_timestamps_file}")
        return audio_timestamps
    except Exception as e:
        logging.error(f"Error loading audio timestamps: {e}")
        return None

def load_accel(accel_file_path):
    try:
        accel_data = pd.read_csv(accel_file_path)
        accel_timestamps = accel_data['Timestamp'].values.astype(np.int64)
        accel_data_array = accel_data[['Accel_X', 'Accel_Y', 'Accel_Z']].values
        logging.info(f"Loaded accelerometer data from {accel_file_path}")
        return accel_data_array, accel_timestamps
    except Exception as e:
        logging.error(f"Error loading accelerometer data: {e}")
        return None, None

def process_noise_data(noise_path, noise_timestamps_path, target_audio_rate):
    noise_data = load_audio(noise_path)
    noise_timestamps = load_audio_timestamps(noise_timestamps_path)
    noise_data = remove_transient_click(noise_data, target_audio_rate, duration_ms=100)
    #use a segment of the noise data as the noise profile
    noise_profile_duration = 3  
    noise_sample_count = int(noise_profile_duration * target_audio_rate)
    noise_profile = noise_data[:noise_sample_count]

    logging.info("Processed noise data for noise reduction")
    return noise_profile

def remove_dc_offset(signal):
    mean_value = np.median(signal, axis=0)
    return signal - mean_value

def bandpass_filter(signal, lowcut, highcut, fs, order=2):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    sos = butter(order, [low, high], btype='band', output='sos')
    filtered_signal = sosfiltfilt(sos, signal, axis=0)
    return filtered_signal

def wavelet_denoising_with_noise_profile_accel(accel_data, noise_profile, wavelet='db4', level=None, threshold_multiplier=0.8):
   
    signal_length = accel_data.shape[0]
    denoised_data = np.zeros_like(accel_data)
    #select an appropriate decomposition level if not provided
    max_level = pywt.dwt_max_level(signal_length, pywt.Wavelet(wavelet))
    if level is None or level > max_level:
        level = min(max_level, 6)
   
    for axis in range(accel_data.shape[1]):
        #apply wavelet decomposition to the noise profile for this axis
        noise_coeffs = pywt.wavedec(noise_profile[:, axis], wavelet, level=level)
        noise_sigma = np.median(np.abs(noise_coeffs[-1])) / 0.6745  #estimate noise level for this axis
        signal_coeffs = pywt.wavedec(accel_data[:, axis], wavelet, level=level) #wavelet decomposition for the signal 
        #denoise coefficients using threshold based on the noise profile for this axis
        denoised_coeffs = []
        for j in range(len(signal_coeffs)):
            #use the noise level from the noise profile for thresholding
            uthresh = threshold_multiplier * noise_sigma * np.sqrt(2 * np.log(len(signal_coeffs[j])))
            denoised_coeffs.append(pywt.threshold(signal_coeffs[j], value=uthresh, mode='soft'))

        reconstructed_signal = pywt.waverec(denoised_coeffs, wavelet) #wavelet reconstruction
        if len(reconstructed_signal) > signal_length:
            reconstructed_signal = reconstructed_signal[:signal_length] 
        elif len(reconstructed_signal) < signal_length:
            print("padded")
            reconstructed_signal = np.pad(reconstructed_signal, (0, signal_length - len(reconstructed_signal)), 'constant')

        denoised_data[:, axis] = reconstructed_signal

    return denoised_data

def notch_filter(data, fs, notch_freq=60.0, quality_factor=30.0):
    nyquist = 0.5 * fs
    norm_notch_freq = notch_freq / nyquist
    b, a = signal.iirnotch(norm_notch_freq, quality_factor)
    return signal.filtfilt(b, a, data)

def wavelet_denoising_with_noise_profile_audio(signal, noise_profile, wavelet='db4', max_level=None, threshold_multiplier=0.7):
    # maximum level of decomposition if not provided
    if max_level is None:
        max_level = pywt.dwt_max_level(len(signal), pywt.Wavelet(wavelet).dec_len)
    
    #wavelet decomposition for the signal and noise profile
    signal_coeffs = pywt.wavedec(signal, wavelet, level=max_level, mode='symmetric')
    noise_coeffs = pywt.wavedec(noise_profile, wavelet, level=max_level, mode='symmetric')
    
   
    denoised_coeffs = [signal_coeffs[0]] #list to store denoised coefficients  
    # Denoise each level using SURE Shrink thresholds
    for i in range(1, len(signal_coeffs)):
        #calculate noise level from the noise profile at the current level using MAD
        level_noise_sigma = np.median(np.abs(noise_coeffs[i] - np.median(noise_coeffs[i]))) / 0.6745
        #calculate SURE Shrink threshold for the detail coefficients at this level
        sure_thresh = level_noise_sigma * np.sqrt(2 * np.log(len(signal_coeffs[i])))
        #apply SURE Shrink thresholding to the signal coefficients at this level
        denoised_detail_coeffs = pywt.threshold(signal_coeffs[i], value=sure_thresh * threshold_multiplier, mode='soft')
        denoised_coeffs.append(denoised_detail_coeffs)
    
    #reconstruct the signal from denoised coefficients
    denoised_signal = pywt.waverec(denoised_coeffs, wavelet, mode='symmetric')
    denoised_signal = denoised_signal[:len(signal)] 
    
    return denoised_signal

def remove_transient_click(signal, sample_rate, duration_ms=100):
    samples_to_remove = int(sample_rate * (duration_ms / 1000))
    trimmed_signal = signal[samples_to_remove:]
    return trimmed_signal

def compute_snr(signal, noise):
    
    signal_power = np.mean(signal ** 2)
    noise_power = np.mean(noise ** 2) + 1e-10  #small epsilon value
    snr = 10 * np.log10(signal_power / noise_power) #SNR in dB
    return snr

def calculate_rmse(original_signal, denoised_signal):
    return np.sqrt(np.mean((original_signal - denoised_signal) ** 2))

def identify_dominant_frequency(frequencies, power_spectrum):
    dominant_frequency = frequencies[np.argmax(power_spectrum)]
    return dominant_frequency

def plot_psd(data, fs, label):
    f, Pxx_den = welch(data, fs, nperseg=1024)
    plt.figure(figsize=(10, 6))
    plt.semilogy(f, Pxx_den)
    plt.title('Power Spectral Density (PSD)')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Power/Frequency (dB/Hz)')
    plt.grid()
    plt.savefig(f'/mnt/c/Users/annam/Desktop/plots/psd_plot_{label}.png')
    plt.close()
    return f, Pxx_den

def process_audio_with_interaction_detection(audio_data, audio_timestamps , start, stop):
    #detect interaction region
    interaction_start, interaction_end = start,stop
    plot_signal(audio_timestamps, audio_data, title="Audio Raw",ylabel="Amplitude", file_name="raw_audio")
    
    #trim both data and timestamps
    audio_data_trimmed = audio_data[interaction_start:interaction_end]
    timestamps_trimmed = audio_timestamps[interaction_start:interaction_end]
    plot_signal(timestamps_trimmed, audio_data_trimmed, title="Audio Data After Trrimming", ylabel="Amplitude",file_name="trimmed_audio")

    plt.figure(figsize=(12, 6))
    plt.plot(audio_data, label="Signal")
    plt.axvline(interaction_start, color='g', linestyle='--', label='Interaction Start')
    plt.axvline(interaction_end, color='r', linestyle='--', label='Interaction End')
    plt.title("Raw Audio Signal with Interaction Region Marked Based on Accelerometer Detection")
    plt.xlabel("Samples")
    plt.ylabel("Amplitude")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/audio_interaction.png')
    plt.close()
    
    print(f"Detected interaction from sample {interaction_start} to {interaction_end}")
    
    return audio_data_trimmed, timestamps_trimmed

def process_audio(audio_data, audio_timestamps, noise_profile,target_audio_rate,start,stop):
    
    audio_data_trimmed,timestamps_trimmed = process_audio_with_interaction_detection(audio_data,audio_timestamps,start,stop)
    #remove DC offset
    audio_data = remove_dc_offset(audio_data_trimmed)
    noise_profile = remove_dc_offset(noise_profile)
    snr = compute_snr(audio_data, noise_profile)
    print(f"SNR before : {snr}")
    plot_signal(timestamps_trimmed, audio_data, title="Audio Data After DC Offset Removal", ylabel="Amplitude",file_name= "dc_audio")

    #notch filter
    plot_psd(audio_data,target_audio_rate,"before_audio")
    frequencies, power_spectrum = plot_psd(noise_profile, target_audio_rate,"noise_before")
    dominant_frequency = identify_dominant_frequency(frequencies, power_spectrum)
    print(f"Dominant Frequency: {dominant_frequency} Hz")
    if dominant_frequency > 0:
        audio_data = notch_filter(audio_data, target_audio_rate, dominant_frequency)
        noise_profile = notch_filter(noise_profile, target_audio_rate, dominant_frequency)
    snr = compute_snr(audio_data, noise_profile)
    print(f"SNR after notch : {snr}")

    #band-pass filter
    audio_data = bandpass_filter(audio_data, lowcut=30, highcut=1000, fs=target_audio_rate, order=5)
    noise_profile = bandpass_filter(noise_profile, lowcut=30, highcut=1000, fs=target_audio_rate, order=5)
    plot_signal(timestamps_trimmed, audio_data, title="Audio Data After Band-Pass Filter", ylabel="Amplitude",file_name= "bandpass_audio")
    snr = compute_snr(audio_data, noise_profile)
    print(f"SNR after bandpass : {snr}")

    #wiener filter
    noise_power = np.mean(noise_profile**2)
    signal_power = np.mean(audio_data**2)
    snr = signal_power / noise_power
    adjusted_noise = noise_power / snr
    audio_denoised = wiener(audio_data, mysize=45, noise=adjusted_noise)
    noise_profile = wiener(noise_profile, mysize=45, noise=adjusted_noise)
            
    snr = compute_snr(audio_denoised, noise_profile)
    print(f"SNR after denoise : {snr}")
    rmse_value = calculate_rmse(audio_data, audio_denoised)
    print(f"RMSE: {rmse_value:.4f}")
    plot_signal(timestamps_trimmed, audio_denoised, title="Audio Data After Wiener Denoising", ylabel="Amplitude",file_name= "denoised_audio_wiener")
    correlation = correlate(audio_denoised, audio_data, mode='full')
    lags = np.arange(-len(audio_denoised) + 1, len(audio_data)) #generate the correct lags array
    max_correlation_index = np.argmax(correlation) #find the index of the maximum correlation
    phase_shift = lags[max_correlation_index] #find the corresponding lag at the maximum correlation
    print(f"Phase shift between the signals audio: {phase_shift} samples")
    
    #wavelet denoising
    audio_denoised_further=wavelet_denoising_with_noise_profile_audio(audio_denoised,noise_profile)
    noise_profile=wavelet_denoising_with_noise_profile_audio(noise_profile,noise_profile)

    snr = compute_snr(audio_denoised_further, noise_profile)
    print(f"SNR after denoise : {snr}")
    rmse_value = calculate_rmse(audio_denoised_further, audio_denoised)
    print(f"RMSE: {rmse_value:.4f}")
    plot_signal(timestamps_trimmed, audio_denoised_further, title="Audio Data After Wavelet Denoising", ylabel="Amplitude",file_name= "denoised_audio")
    correlation = correlate(audio_denoised, audio_denoised_further, mode='full')
    lags = np.arange(-len(audio_denoised) + 1, len(audio_denoised_further)) #generate the correct lags array
    max_correlation_index = np.argmax(correlation) #find the index of the maximum correlation
    phase_shift = lags[max_correlation_index] #find the corresponding lag at the maximum correlation
    print(f"Phase shift between the signals audio further: {phase_shift} samples")
    plot_psd(audio_denoised_further,target_audio_rate,"after_audio")
    plot_psd(noise_profile, target_audio_rate,"noise_after")

    return audio_denoised_further, timestamps_trimmed

def rms_detection_accel(accel_data, window_size=100, threshold_multiplier=6):
    signal_length = len(accel_data)
    #RMS energy using a moving window
    rms_energy = np.array([np.sqrt(np.mean(accel_data[i:i+window_size]**2)) for i in range(signal_length - window_size)])
    rms_energy = np.pad(rms_energy, (window_size//2, window_size//2), 'edge') #pad the RMS energy to match the original signal length
    threshold = threshold_multiplier * np.median(rms_energy) #threshold based on the median energy
    interaction_indices = np.where(rms_energy > threshold)[0]
    if len(interaction_indices) == 0:
        print("No significant interaction detected.")
        return 0, signal_length
    interaction_start = interaction_indices[0]
    interaction_end = interaction_indices[-1]
    
    #plot the original signal and the detected interaction region
    plt.figure(figsize=(10, 6))
    plt.plot(accel_data, label='Original Signal')
    plt.axvline(x=interaction_start, color='g', linestyle='--', label='Interaction Start')
    plt.axvline(x=interaction_end, color='r', linestyle='--', label='Interaction End')
    plt.legend()
    plt.title("RMS-Based Interaction Detection (Single Axis)")
    plt.xlabel("Samples")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/rms_interaction_detection_single_axis.png')
    plt.close()

    print(f"Detected interaction from sample {interaction_start} to {interaction_end}")
    
    return interaction_start, interaction_end

def process_accel_with_interaction_detection(accel_data, accel_timestamps):
    #detect interaction region
    interaction_start, interaction_end = rms_detection_accel(accel_data[:, 1])
    plot_accel_signal(accel_timestamps, accel_data, title="Accelerometer Raw", file_name="raw_accel")
    
    #trim both data and timestamps
    accel_data_trimmed = accel_data[interaction_start:interaction_end]
    timestamps_trimmed = accel_timestamps[interaction_start:interaction_end]
    plot_accel_signal(timestamps_trimmed, accel_data_trimmed, title="Accelerometer Data After Trrimming", file_name="trimmed_accel")
    sample_rate_ratio = 48000 / 800
    
    #convert accelerometer indices to audio indices
    interaction_start = int(interaction_start * sample_rate_ratio)
    interaction_end = int(interaction_end * sample_rate_ratio)

    
    return accel_data_trimmed, timestamps_trimmed,interaction_start,interaction_end

def calculate_dominant_frequency_notch(noise_profile, fs):
    dominant_frequencies = []
    
    for axis in range(noise_profile.shape[1]):  #iterate over X, Y, Z axes
        freqs, psd = signal.welch(noise_profile[:, axis], fs, nperseg=min(1024, len(noise_profile[:, axis])))
        dominant_freq = freqs[np.argmax(psd)] 
        dominant_frequencies.append(dominant_freq)
        print(f"Dominant frequency for axis {axis}: {dominant_freq} Hz")
    
    return dominant_frequencies

def process_accel(accel_data_array, accel_timestamps, target_accel_rate):
    #find the interaction region and trim the signal
    accel_data_trimmed, timestamps_trimmed,start,stop = process_accel_with_interaction_detection(accel_data_array, accel_timestamps)
    #define noise profile
    noise_profile = accel_data_array[:int(target_accel_rate)]  # 1 second of noise
    noise_profile = remove_dc_offset(noise_profile)

    #remove DC offset
    accel_data_trimmed = remove_dc_offset(accel_data_trimmed)
    plot_accel_signal(timestamps_trimmed, accel_data_trimmed, title="Accelerometer Data After DC Removal", file_name="DC_accel")
    snr = compute_snr(accel_data_trimmed, noise_profile)
    print(f"SNR accel (dc offset): {snr}")
    plot_psd(accel_data_trimmed[:,1],target_accel_rate,"accel_before")

    #notch filter
    dominant_frequencies = calculate_dominant_frequency_notch(noise_profile, target_accel_rate)
    accel_data_filtered = np.zeros_like(accel_data_trimmed)
    for axis in range(accel_data_trimmed.shape[1]): 
        accel_data_filtered[:, axis] = notch_filter(accel_data_trimmed[:, axis], target_accel_rate, dominant_frequencies[axis])

    noise_profile_notch = np.zeros_like(noise_profile)
    for axis in range(noise_profile.shape[1]):  
        noise_profile_notch[:, axis] = notch_filter(noise_profile[:, axis], target_accel_rate, dominant_frequencies[axis])

    snr = compute_snr(accel_data_filtered, noise_profile_notch)
    print(f"SNR accel (notch): {snr}")
    noise_profile=noise_profile_notch
        
    #band-pass filter
    accel_data_filtered = bandpass_filter(accel_data_filtered, lowcut=30, highcut=350, fs=target_accel_rate)
    noise_profile = bandpass_filter(noise_profile, lowcut=30, highcut=350, fs=target_accel_rate)
    snr = compute_snr(accel_data_filtered, noise_profile)
    print(f"SNR accel (bandpass): {snr}")
    plot_accel_signal(timestamps_trimmed, accel_data_filtered, title="Accelerometer Data After Band-Pass Filter", file_name="bandpass_accel")
    
    #wavelet denoising 
    accel_data_denoised = wavelet_denoising_with_noise_profile_accel(accel_data_filtered, noise_profile, wavelet='db4', threshold_multiplier=0.8)
    noise_profile = wavelet_denoising_with_noise_profile_accel(noise_profile, noise_profile, wavelet='db4',  threshold_multiplier=0.8)

    snr = compute_snr(accel_data_denoised, noise_profile)
    print(f"SNR accel (denoised): {snr}")
    plot_accel_signal(timestamps_trimmed, accel_data_denoised, title="Accelerometer Data After Wavelet Denoising", file_name="denoised_accel")

    
    correlation = correlate(accel_data_denoised[:, 1], accel_data_filtered[:, 1], mode='full') #cross-correlation
    lags = np.arange(-len(accel_data_denoised[:, 1]) + 1, len(accel_data_filtered[:, 1])) #generate the correct lags array
    max_correlation_index = np.argmax(correlation) #find the index of the maximum correlation
    phase_shift = lags[max_correlation_index]#find the corresponding lag at the maximum correlation
    print(f"Phase shift between the signals: {phase_shift} samples")
    plot_psd(accel_data_denoised[:,1],target_accel_rate,"accel_after")
    logging.info("Processed accelerometer data")
    return accel_data_denoised, timestamps_trimmed, start, stop

def adaptive_peak_detection(signal, sample_rate, prominence_percentile=93, distance_factor=0.03, height_multiplier=1.5):
    #calculate adaptive height threshold on smoothed signal
    height_threshold = np.percentile(np.abs(signal), prominence_percentile)
    distance_threshold = int(distance_factor * sample_rate)
    #detect peaks on the smoothed signal
    peaks, _ = find_peaks(signal, height=height_threshold, distance=distance_threshold)
    #filter peaks based on original signal's median amplitude
    filtered_peaks = [p for p in peaks if signal[p] <= height_multiplier * np.median(signal[peaks])]
    return filtered_peaks

def detect_consistent_region(signal, sample_rate, min_cluster_size=1, tag="none"):
     #set baseline values based on the signal type
    if tag == "accel":
        peaks = adaptive_peak_detection(signal, sample_rate, prominence_percentile=78, distance_factor=0.03, height_multiplier=1.8)
        base_tolerance_factor = 0.25
        base_min_cluster_size = 3
    elif tag == "audio":
        peaks = adaptive_peak_detection(signal, sample_rate, prominence_percentile=86, distance_factor=0.028, height_multiplier=1.5)
        base_tolerance_factor = 0.4
        base_min_cluster_size = 5

    #plot detected peaks
    plt.figure(figsize=(10, 4))
    plt.plot(signal, label="Signal")
    plt.plot(peaks, signal[peaks], "rx", label="Detected Peaks")
    plt.title("Detected Peaks in Signal")
    plt.xlabel("Sample")
    plt.ylabel("Amplitude")
    plt.legend()
    plt.grid(True)
    plt.savefig(f'/mnt/c/Users/annam/Desktop/plots/detected_peaks_{tag}.png')
    plt.close()

    if len(peaks) < base_min_cluster_size:
        print("Not enough peaks found for clustering.")
        return 0, len(signal) - 1

    #calculate distances between consecutive peaks
    peak_distances = np.diff(peaks)
    median_distance = np.median(peak_distances)
    distance_iqr = np.percentile(peak_distances, 75) - np.percentile(peak_distances, 25)

    #calculate density ratio
    density_ratio = distance_iqr / median_distance

    #set default tolerance and min_cluster_size based on density and signal type
    if density_ratio < 0.4:  #sense peaks
        tolerance_factor = base_tolerance_factor + 0.2  #looser tolerance for dense peaks
        min_cluster_size = base_min_cluster_size + 2  #increase min cluster size for dense regions
    else:  
        tolerance_factor = max(0.4, base_tolerance_factor) 
        min_cluster_size = base_min_cluster_size  

    #calculate tolerance based on adjusted tolerance factor
    tolerance = distance_iqr if distance_iqr < median_distance * tolerance_factor else median_distance * tolerance_factor
    lower_bound = median_distance - tolerance
    upper_bound = median_distance + tolerance

    #cluster regions with consistent peak spacing
    consistent_peaks = []
    temp_cluster = [peaks[0]]
    for i in range(1, len(peaks)):
        if lower_bound <= peak_distances[i - 1] <= upper_bound:
            temp_cluster.append(peaks[i])
        else:
            if len(temp_cluster) >= min_cluster_size:
                consistent_peaks.append(temp_cluster)
            temp_cluster = [peaks[i]]
    if len(temp_cluster) >= min_cluster_size:
        consistent_peaks.append(temp_cluster)

    #select the longest cluster as the consistent region
    if consistent_peaks:
        best_cluster = max(consistent_peaks, key=len)
        start_index = best_cluster[0]
        stop_index = best_cluster[-1]
    else:
        print("No consistent region found; using the entire signal.")
        start_index, stop_index = 0, len(signal) - 1

    #plot the consistent region for visual verification
    plt.figure(figsize=(10, 4))
    plt.plot(signal, label="Signal")
    plt.plot(peaks, signal[peaks], "rx", label="Detected Peaks")
    plt.axvline(start_index, color='green', linestyle='--', label="Start of Consistent Region")
    plt.axvline(stop_index, color='red', linestyle='--', label="End of Consistent Region")
    plt.title("Consistent Region Detection")
    plt.xlabel("Sample")
    plt.ylabel("Amplitude")
    plt.legend()
    plt.grid(True)
    plt.savefig(f'/mnt/c/Users/annam/Desktop/plots/consistent_region_{tag}.png')
    plt.close()

    return start_index, stop_index

def trim_signals(audio_signal, audio_timestamps,accel_signal, accel_timestamps, interaction_region_audio, interaction_region_accel):
    start_idx_audio,end_idx_audio = interaction_region_audio
    start_idx_accel,end_idx_accel = interaction_region_accel
    audio_trimmed = audio_signal[start_idx_audio:end_idx_audio]
    audio_trimmed_timestamps = audio_timestamps[start_idx_audio:end_idx_audio]
    accel_trimmed_timestamps = accel_timestamps[start_idx_accel:end_idx_accel]
    accel_trimmed = accel_signal[start_idx_accel:end_idx_accel, :]
    logging.info("Trimmed signals based on interaction region")
    return audio_trimmed, audio_trimmed_timestamps, accel_trimmed ,accel_trimmed_timestamps

def save_audio_as_wav(audio_data, sample_rate, output_wav_path):
    sf.write(output_wav_path, audio_data, sample_rate, subtype='PCM_24')
    logging.info(f"Audio saved as WAV file: {output_wav_path}")

def save_accel_as_csv(accel_data, output_csv_path):
    accel_df = pd.DataFrame(accel_data, columns=['Accel_X', 'Accel_Y', 'Accel_Z'])
    accel_df.to_csv(output_csv_path, index=False)
    logging.info(f"Accelerometer data saved to {output_csv_path}")

def compute_amplitude_envelope(signal):
    analytic_signal = hilbert(signal)
    amplitude_envelope = np.abs(analytic_signal)
    return amplitude_envelope

def plot_amplitude_envelopes(time_audio, audio_envelope, time_accel, accel_magnitude):
    
    #plot both signals and their standard deviations
    fig, ax1 = plt.subplots(figsize=(14, 6))
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Audio Signal', color='blue')
    ax1.plot(time_audio, audio_envelope, label='Audio Rolling Std', color='cyan', alpha=0.6)
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx() 
    ax2.set_ylabel('Accelerometer Y-axis (g)', color='orange')  
    ax2.plot(time_accel, accel_magnitude, label='Accel Y-axis Rolling Std', color='red', alpha=0.6)
    ax2.tick_params(axis='y', labelcolor='orange')

    fig.tight_layout() 
    plt.title('Audio and Accelerometer Signal with Rolling Standard Deviation')
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/amplitude_envelopes.png')
    plt.close()

def plot_combined_std(timestamps_audio, audio_signal, accel_signal,timestamps_accel ,window_size_audio, window_size_accel):

    time_audio = (timestamps_audio - timestamps_audio[0]) / 1e6  #convert microseconds to seconds
    time_accel = (timestamps_accel - timestamps_accel[0]) / 1e6

    num_samples = int(len(audio_signal) * 800 / 48000)
    downsampled_audio = signal.resample(audio_signal, num_samples)
    audio_std = pd.Series(downsampled_audio).rolling(window=window_size_audio, min_periods=1).std()
    accel_std = pd.Series(accel_signal).rolling(window=window_size_accel, min_periods=1).std()

    #plot both signals and their standard deviations
    fig, ax1 = plt.subplots(figsize=(14, 6))

    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Audio Signal', color='blue')
    ax1.plot( audio_std, label='Audio Rolling Std', color='cyan', alpha=0.6)
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    ax2.set_ylabel('Accelerometer Y-axis (g)', color='orange')  
    ax2.plot(accel_std, label='Accel Y-axis Rolling Std', color='red', alpha=0.6)
    ax2.tick_params(axis='y', labelcolor='orange')

    fig.tight_layout()  # adjust layout
    plt.title('Audio and Accelerometer Signal with Rolling Standard Deviation')
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/std.png')
    plt.close()

def compute_cross_correlation(signal1, signal2):
    correlation = np.correlate(signal1, signal2, mode='full')
    lags = np.arange(-len(signal2) + 1, len(signal1))
    return correlation, lags

def validate_alignment(audio_signal, audio_timestamps, accel_signal, accel_timestamps):
 
    num_samples = int(len(audio_signal) * 800 / 48000)
    downsampled_audio = signal.resample(audio_signal, num_samples)
    audio_energy = np.abs(hilbert(downsampled_audio)) ** 2
    accel_energy = np.abs(hilbert(accel_signal)) ** 2
    audio_energy /= np.max(audio_energy)
    accel_energy /= np.max(accel_energy)
    correlation = correlate(audio_energy, accel_energy, mode='full')
    lags = np.arange(-len(accel_energy) + 1, len(audio_energy))
    max_corr_lag = lags[np.argmax(correlation)]
    logging.info(f"Maximum correlation lag after alignment: {max_corr_lag} samples")

    #plot cross-correlation 
    plt.figure(figsize=(10, 6))
    plt.plot(lags, correlation)
    plt.title('Cross-Correlation Between Audio and Accelerometer Signals After Alignment')
    plt.xlabel('Lag (samples)')
    plt.ylabel('Correlation')
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/validated_alignment.png')
    plt.close()
    return max_corr_lag

def visualize_alignment_with_interaction(timestamps_audio, audio_signal, accel_signal, adjusted_accel_timestamps, interaction_region_audio,interaction_region_accel):
 
    time_audio = (timestamps_audio - timestamps_audio[0]) / 1e6  #convert microseconds to seconds
    time_accel = (adjusted_accel_timestamps - adjusted_accel_timestamps[0]) / 1e6

    audio_start_idx , audio_end_idx = interaction_region_audio
    accel_start_idx, accel_end_idx = interaction_region_accel

    plt.figure(figsize=(14, 6))
    #audio signal plot
    plt.subplot(2, 1, 1)
    plt.plot(time_audio, audio_signal, label='Audio Signal')
    plt.axvline(x=time_audio[audio_start_idx], color='red', linestyle='--', label='Interaction Start')
    plt.axvline(x=time_audio[audio_end_idx], color='green', linestyle='--', label='Interaction End')
    plt.title('Audio Signal with Interaction Points')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.legend()
    plt.grid(True)
    #accelerometer signal plot (Y-axis)
    plt.subplot(2, 1, 2)
    plt.plot(time_accel, accel_signal[:, 1], label='Accelerometer Y-axis', color='orange')
    plt.axvline(x=time_accel[accel_start_idx], color='red', linestyle='--', label='Interaction Start')
    plt.axvline(x=time_accel[accel_end_idx], color='green', linestyle='--', label='Interaction End')
    plt.title('Accelerometer Signal with Interaction Points (Y-axis)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/aligned_signals_with_interaction_points.png')
    plt.close()
    logging.info("Visualized the alignment of audio and accelerometer signals with interaction points")

def min_max_normalize(signal, range_min=-1, range_max=1):
    signal_min = np.min(signal)
    signal_max = np.max(signal)
    normalized_signal = (signal - signal_min) / (signal_max - signal_min) 
    normalized_signal = normalized_signal * (range_max - range_min) + range_min 
    return normalized_signal

def plot_signals(audio_data, accel_data, audio_timestamps, accel_timestamps):
    #normalize audio and accelerometer signals for comparison
    audio_normalized = min_max_normalize(audio_data)
    accel_normalized = min_max_normalize(accel_data)
   
    time_audio = (audio_timestamps - audio_timestamps[0]) / 1e6  #in seconds
    time_accel = (accel_timestamps - accel_timestamps[0]) / 1e6 

    #plot the signals
    plt.figure(figsize=(14, 6))
    plt.plot(time_audio, audio_normalized, label='Normalized Audio Signal', color='cyan', alpha=0.6)
    plt.plot(time_accel, accel_normalized[:, 1], label='Normalized Accelerometer Y-axis', color='red', alpha=0.6)  
    plt.title('Aligned Audio and Accelerometer Signals')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Normalized Amplitude')
    plt.legend()
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/aligned_signals_normalized.png')
    plt.close()
    print("Signals plotted and saved.")

def analyze_sample_intervals(timestamps, expected_rate):
    expected_interval = 1e6 / expected_rate  #microseconds per sample
    actual_intervals = np.diff(timestamps)
    deviations = actual_intervals - expected_interval #deviation from the expected interval
 
    print(f"Expected interval: {expected_interval} microseconds")
    print(f"Mean deviation: {np.mean(deviations)} microseconds")
    print(f"Max deviation: {np.max(deviations)} microseconds")
    print(f"Min deviation: {np.min(deviations)} microseconds")
   
    plt.plot(actual_intervals)
    plt.title("Actual Time Intervals Between Samples")
    plt.xlabel("Sample index")
    plt.ylabel("Interval (microseconds)")
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/timestamps.png')
    plt.close()
    return deviations

def analyze_sample_intervals_accel(timestamps, expected_rate):
   
    expected_interval = 1e6 / expected_rate  #microseconds per sample
    actual_intervals = np.diff(timestamps)
    deviations = actual_intervals - expected_interval

    print(f"Expected interval: {expected_interval} microseconds")
    print(f"Mean deviation: {np.mean(deviations)} microseconds")
    print(f"Max deviation: {np.max(deviations)} microseconds")
    print(f"Min deviation: {np.min(deviations)} microseconds")

    plt.plot(actual_intervals)
    plt.title("Actual Time Intervals Between Samples")
    plt.xlabel("Sample index")
    plt.ylabel("Interval (microseconds)")
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/timestamps_accel.png')
    plt.close()
    
    return deviations

def track_drift_over_time(timestamps, expected_interval, label):

    actual_intervals = np.diff(timestamps)
    print(actual_intervals)
    deviations = actual_intervals - expected_interval
    
    plt.figure(figsize=(12, 6))
    plt.plot(deviations, label=f'{label} Deviations')
    plt.axhline(0, color='r', linestyle='--')
    plt.xlabel('Sample Index')
    plt.ylabel('Deviation from Expected Interval (microseconds)')
    plt.title(f'{label} Signal Drift Over Time')
    plt.grid(True)
    plt.savefig(f'/mnt/c/Users/annam/Desktop/plots/deviations_{label}.png')
    plt.close()
    
    return deviations

def check_sampling_rate_consistency(timestamps, expected_rate, label):
    #actual duration based on the first and last timestamp
    actual_duration = (timestamps[-1] - timestamps[0]) / 1e6  #in seconds
    actual_samples = len(timestamps)
    actual_rate = actual_samples / actual_duration  #actual sample rate
    
    print(f"Expected rate {label}: {expected_rate}, Actual rate: {actual_rate}")
    return actual_rate

def calculate_drift(original_timestamps, expected_duration):
    actual_duration = (original_timestamps[-1] - original_timestamps[0]) / 1e6  #microseconds to seconds
    drift = actual_duration - expected_duration
    return drift, actual_duration

def main():

    #file paths and signal loading
    audio_file_path = '/mnt/c/Users/annam/Desktop/data/sandpaper1.raw'
    audio_timestamps_file = '/mnt/c/Users/annam/Desktop/data/sandpaper1.txt'
    accel_file_path = '/mnt/c/Users/annam/Desktop/data/sandpaper1.csv'
    noise_path = '/mnt/c/Users/annam/Desktop/data/noise.raw'
    noise_timestamps_path = '/mnt/c/Users/annam/Desktop/data/noise.txt'
    output_wav_path = '/mnt/c/Users/annam/Desktop/final/sandpaper.wav'
    output_csv_path = '/mnt/c/Users/annam/Desktop/final/sandpaper.csv'
    target_audio_rate = 48000
    target_accel_rate = 800
    audio_data = load_audio(audio_file_path)
    audio_timestamps_original = load_audio_timestamps(audio_timestamps_file)
    accel_data_array, accel_timestamps_original = load_accel(accel_file_path)

    #CHECKS FOR TIMESTAMPS AND DRIFTS
    analyze_sample_intervals_accel(accel_timestamps_original,800)
    drift, actual_duration = calculate_drift(accel_timestamps_original, 4.0)
    print(f"Drift Accel: {drift} seconds, Actual Duration: {actual_duration} seconds")
    analyze_sample_intervals(audio_timestamps_original,48000)
    drift, actual_duration = calculate_drift(audio_timestamps_original, 4.0)
    print(f"Drift Audio: {drift} seconds, Actual Duration: {actual_duration} seconds")
    expected_audio_interval = 1e6 / 48000  #20.83 microseconds for audio
    expected_accel_interval = 1e6 / 800  #1250 microseconds for accelerometer
    check_sampling_rate_consistency(accel_timestamps_original, 800 ,  "Accel")
    check_sampling_rate_consistency(audio_timestamps_original, 48000 ,  "Audio")
    track_drift_over_time(audio_timestamps_original, expected_audio_interval, "Audio")
    track_drift_over_time(accel_timestamps_original, expected_accel_interval, "Accelerometer")

    #correct initial offset
    audio_start_time_us = audio_timestamps_original[0]
    accel_start_time_us = accel_timestamps_original[0]
    time_offset_us = accel_start_time_us - audio_start_time_us
    if time_offset_us > 0:
        accel_timestamps_aligned = accel_timestamps_original - time_offset_us
        audio_timestamps_aligned = audio_timestamps_original
    else:
        accel_timestamps_aligned = accel_timestamps_original
        audio_timestamps_aligned = audio_timestamps_original + abs(time_offset_us)
    #reconstruct expected timestamps
    audio_sample_interval_us = 1_000_000 / target_audio_rate  
    accel_sample_interval_us = 1_000_000 / target_accel_rate  
    num_audio_samples = len(audio_data)
    num_accel_samples = len(accel_data_array)
    reconstructed_audio_timestamps = audio_timestamps_aligned[0] + np.arange(num_audio_samples) * audio_sample_interval_us
    reconstructed_accel_timestamps = accel_timestamps_aligned[0] + np.arange(num_accel_samples) * accel_sample_interval_us
    #Accel Signal
    start_time_accel = reconstructed_accel_timestamps[0]
    end_time_accel = reconstructed_accel_timestamps[-1]
    duration_accel_us = end_time_accel - start_time_accel
    num_samples_accel = int(np.round(duration_accel_us / 1e6 * target_accel_rate)) + 1
    uniform_accel_timestamps = start_time_accel + np.arange(num_samples_accel) * (1e6 / target_accel_rate)
    #interpolate accelerometer data onto uniformly spaced timestamps for all axes
    num_axes = accel_data_array.shape[1]
    uniform_accel_data = np.zeros((len(uniform_accel_timestamps), num_axes))
    for i in range(num_axes):
        accel_interp_func = interp1d(reconstructed_accel_timestamps, accel_data_array[:, i], kind='linear', bounds_error=False, fill_value="extrapolate")
        uniform_accel_data[:, i] = accel_interp_func(uniform_accel_timestamps)
    #Audio Signal
    start_time_audio = reconstructed_audio_timestamps[0]
    end_time_audio = reconstructed_audio_timestamps[-1]
    duration_audio_us = end_time_audio - start_time_audio
    num_samples_audio = int(np.round(duration_audio_us / 1e6 * target_audio_rate)) + 1
    uniform_audio_timestamps = start_time_audio + np.arange(num_samples_audio) * (1e6 / target_audio_rate)
    #interpolate audio data onto uniformly spaced timestamps
    audio_interp_func = interp1d(reconstructed_audio_timestamps, audio_data, kind='linear', bounds_error=False, fill_value="extrapolate")
    uniform_audio_data = audio_interp_func(uniform_audio_timestamps)

    
    uniform_accel_time_s = (uniform_accel_timestamps - uniform_accel_timestamps[0]) / 1e6
    uniform_audio_time_s = (uniform_audio_timestamps - uniform_audio_timestamps[0]) / 1e6
    uniform_audio_data_norm = uniform_audio_data / np.max(np.abs(uniform_audio_data))
    uniform_accel_data_norm = uniform_accel_data / np.max(np.abs(uniform_accel_data))

    #plot the signals
    plt.figure(figsize=(12, 6))
    plt.plot(uniform_audio_time_s, uniform_audio_data_norm, label='Audio Signal')
    plt.plot(uniform_accel_time_s, uniform_accel_data_norm, label=f'Accelerometer')
    plt.xlabel('Time (s)')
    plt.ylabel('Normalized Amplitude')
    plt.title('Aligned Signals After Non-Linear Drift Correction')
    plt.legend()
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/after_non_linear.png')
    plt.close()

    accel_data_array = uniform_accel_data
    accel_timestamps_original = uniform_accel_timestamps
    audio_data = uniform_audio_data
    audio_timestamps_original = uniform_audio_timestamps
 
##########################################################################################################################################################################################################################################################
    #initial transient removal
    accel_data_array = remove_transient_click(accel_data_array, target_accel_rate, duration_ms=100)
    accel_timestamps_original = accel_timestamps_original[len(accel_timestamps_original) - len(accel_data_array):]
    audio_data = remove_transient_click(audio_data, target_audio_rate, duration_ms=100)
    audio_timestamps_original = audio_timestamps_original[len(audio_timestamps_original) - len(audio_data):]
    plot_signals(audio_data, accel_data_array, audio_timestamps_original, accel_timestamps_original)
  
    noise_profile = process_noise_data(noise_path, noise_timestamps_path, target_audio_rate)

    #PROCESS SIGNALS
    accel_data_processed, accel_timestamps_processed,start,stop = process_accel(accel_data_array, accel_timestamps_original, target_accel_rate)
    audio_data_processed, audio_timestamps_processed = process_audio(audio_data, audio_timestamps_original, noise_profile, target_audio_rate, start, stop)

    audio_amplitude_envelope = compute_amplitude_envelope(audio_data_processed)
    #accel_magnitude =  np.linalg.norm(accel_data_processed, axis=1)
    accel_magnitude =  compute_amplitude_envelope(accel_data_processed[:, 1])
    time_audio = (audio_timestamps_processed - audio_timestamps_processed[0]) / 1e6  
    time_accel = (accel_timestamps_processed - accel_timestamps_processed[0]) / 1e6  
    plot_amplitude_envelopes(time_audio, audio_amplitude_envelope, time_accel, accel_magnitude)
    
    #consistent interaction region detection
    audio_start_idx, audio_end_idx = detect_consistent_region(audio_data_processed, sample_rate=48000, tag="audio")
    accel_start_idx, accel_end_idx = detect_consistent_region(accel_data_processed[:,1], sample_rate=800,  tag="accel")

    accel_start_time = accel_start_idx / target_accel_rate
    accel_end_time = accel_end_idx / target_accel_rate
    audio_start_time = audio_start_idx / target_audio_rate
    audio_end_time = audio_end_idx / target_audio_rate
    #find the common start and end times of the interaction region
    common_start_time = max(audio_start_time, accel_start_time)
    common_end_time = min(audio_end_time, accel_end_time)
    #convert common times back to indices for each signal
    audio_start_idx_common = int(common_start_time * target_audio_rate)
    audio_end_idx_common = int(common_end_time * target_audio_rate)
    accel_start_idx_common = int(common_start_time * target_accel_rate)
    accel_end_idx_common = int(common_end_time * target_accel_rate)
    #set the interaction region for both audio and accelerometer signals
    interaction_region_audio = (audio_start_idx_common, audio_end_idx_common)
    interaction_region_accel = (accel_start_idx_common, accel_end_idx_common)

    visualize_alignment_with_interaction(audio_timestamps_processed, audio_data_processed, accel_data_processed,accel_timestamps_processed, 
                                         interaction_region_audio,interaction_region_accel)

    audio_trimmed, audio_trimmed_timestamps, accel_trimmed, accel_trimmed_timestamps = trim_signals(audio_data_processed, audio_timestamps_processed, 
                                                                                                    accel_data_processed,accel_timestamps_processed,
                                                                                                    interaction_region_audio,interaction_region_accel)

   #calculate velocity for the interaction region
    velocity_y_interaction = calculate_velocity_from_accel(accel_trimmed[:, 1], accel_trimmed_timestamps)
    base_velocity_y = np.mean(np.abs(velocity_y_interaction))  
    print(f"Base velocity during interaction: {base_velocity_y:.4f} m/s")

    visualize_trimmed_final_both(audio_trimmed_timestamps, audio_trimmed, accel_trimmed,accel_trimmed_timestamps)
    validate_alignment(audio_trimmed, audio_trimmed_timestamps, accel_trimmed[:,1], accel_trimmed_timestamps)
    plot_combined_std(audio_trimmed_timestamps, audio_trimmed, accel_trimmed[:,1], accel_trimmed_timestamps, window_size_audio=10000, window_size_accel=10000)
    
    #save processed data
    save_audio_as_wav(audio_trimmed, target_audio_rate, output_wav_path)
    save_accel_as_csv(accel_trimmed, output_csv_path)

def calculate_velocity_from_accel(accel_y, timestamps):
    time_diffs = np.diff(timestamps) / 1e6 #time differences between each sample in seconds
    #trapezoidal integral manually using cumulative sum
    velocity_y = np.zeros(len(accel_y)) 
    velocity_y[1:] = np.cumsum((accel_y[:-1] + accel_y[1:]) / 2 * time_diffs)
    return velocity_y

def visualize_trimmed_final_both(audio_timestamps_processed, audio_signal, accel_signal, adjusted_accel_timestamps):
    #
    time_audio = (audio_timestamps_processed - audio_timestamps_processed[0]) / 1e6  # in seconds
    time_accel = (adjusted_accel_timestamps - adjusted_accel_timestamps[0]) / 1e6  # in seconds
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Audio Signal', color='blue')
    ax1.plot( time_audio, audio_signal, label='Audio Signal', color='cyan', alpha=0.6)
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()
    ax2.set_ylabel('Accelerometer Y-axis ', color='orange')
    ax2.plot(time_accel, accel_signal[:,1], label='Accelerometer Y-axis', color='red', alpha=0.4)
    ax2.tick_params(axis='y', labelcolor='orange')
    
    plt.title('Trimmed Audio and Accelerometer Signals at Original Sampling Rates')
    plt.grid(True)
    plt.savefig('/mnt/c/Users/annam/Desktop/plots/trimmed_final_both.png', bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    main()