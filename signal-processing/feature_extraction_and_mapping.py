import numpy as np
import pandas as pd
import librosa
import matplotlib.pyplot as plt
import os
from scipy.signal import find_peaks
from scipy.stats import kurtosis, skew


audio_sample_rate = 48000  
accel_sample_rate = 800   

all_audio_paths = ['/mnt/c/Users/annam/Desktop/final/comb_mikro.wav', '/mnt/c/Users/annam/Desktop/final/comb_megalo.wav', '/mnt/c/Users/annam/Desktop/final/sandpaper.wav']
all_accel_paths = ['/mnt/c/Users/annam/Desktop/final/comb_mikro.csv', '/mnt/c/Users/annam/Desktop/final/comb_megalo.csv', '/mnt/c/Users/annam/Desktop/final/sandpaper.csv']

def extract_audio_features_per_segment(segment, sample_rate):
    n_fft = min(len(segment), 512)  #adjust n_fft for better resolution
    hop_length = n_fft // 4         #overlap for smoother features
 
    #Spectral Features
    spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=segment, sr=sample_rate, n_fft=n_fft, hop_length=hop_length))
    spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=segment, sr=sample_rate, n_fft=n_fft, hop_length=hop_length))
    spectral_flatness = np.mean(librosa.feature.spectral_flatness(y=segment, n_fft=n_fft, hop_length=hop_length))
    spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(y=segment, sr=sample_rate, n_fft=n_fft, hop_length=hop_length))
    spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=segment, sr=sample_rate, n_fft=n_fft, hop_length=hop_length))


    #Temporal Features
    rms = np.mean(librosa.feature.rms(y=segment, frame_length=n_fft, hop_length=hop_length))
    envelope_mean = np.mean(np.abs(segment))

    #STE calculation: breaking down the segment into smaller frames within the segment
    frame_length = int(0.01 * sample_rate)  # 10ms frames
    frame_hop = frame_length // 2  # 50% overlap for STE calculation
    ste_frames = np.array([np.sum(segment[i:i+frame_length] ** 2) for i in range(0, len(segment) - frame_length + 1, frame_hop)])
    ste = np.mean(ste_frames)

    zcr = np.mean(librosa.feature.zero_crossing_rate(y=segment, frame_length=n_fft, hop_length=hop_length))
    onset_env = np.mean(librosa.onset.onset_strength(y=segment, sr=sample_rate, hop_length=hop_length))
    chroma = np.mean(librosa.feature.chroma_stft(y=segment, sr=sample_rate, n_fft=n_fft, hop_length=hop_length))
    spectral_flux = np.mean(np.diff(np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length)), axis=1))

    #energy Entropy: calculate entropy of power spectral density
    ps = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length))**2
    ps_norm = ps / np.sum(ps, axis=0, keepdims=True)
    energy_entropy = -np.sum(ps_norm * np.log(ps_norm + 1e-10), axis=0).mean()

    peak_rms_ratio = np.max(np.abs(segment)) / np.sqrt(np.mean(segment ** 2))  #peak-to-RMS Ratio
    loudness = np.mean(librosa.feature.spectral_flatness(y=segment))  

    n_mels = 40 #reduce number of mel filters to avoid empty filters
    #MFCCs: Use the mean and variance of coefficients (scalars)
    mfcc = librosa.feature.mfcc(y=segment, sr=sample_rate, n_mfcc=13, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels, fmax=1000)
    mfcc_mean = np.mean(mfcc)  
    mfcc_var = np.var(mfcc)   

    return {
        'mfcc_mean': mfcc_mean,
        'mfcc_var': mfcc_var,
        'spectral_centroid': spectral_centroid,
        'spectral_bandwidth': spectral_bandwidth,
        'spectral_flatness': spectral_flatness,
        'spectral_contrast': spectral_contrast,
        'spectral_rolloff': spectral_rolloff,
        'rms': rms,
        'ste': ste, 
        'zcr': zcr,
        'onset_strength_mean': onset_env,
        'chroma_mean': chroma,
        'spectral_flux': spectral_flux,
        'energy_entropy': energy_entropy,
        'peak_rms_ratio': peak_rms_ratio,
        'loudness': loudness,
        'envelope_mean' : envelope_mean,
        'rms' : rms
    }

def extract_peak_features(segment, percentile_factor=0.75, prominence_factor=0.1):
    #dynamic threshold based on segment percentile
    threshold = np.percentile(segment, percentile_factor * 100)
    #dynamic prominence based on the signal's variability
    prominence = prominence_factor * np.std(segment)
    peaks, _ = find_peaks(segment, height=threshold, prominence=prominence)
    #calculate peak count and average peak height
    peak_count = len(peaks)
    peak_height_mean = np.mean(segment[peaks]) if peak_count > 0 else 0
    return peak_count, peak_height_mean

def extract_accel_features_per_segment(segment, sample_rate):
    segment_len = len(segment)
    #dynamic FFT settings based on segment length
    n_fft = min(segment_len, max(64, segment_len // 2))  #n_fft is not too small
    hop_length = n_fft // 2

    #Time-Domain Features
    rms = np.sqrt(np.mean(np.square(segment)))
    mean_value = np.mean(segment)
    std_dev = np.std(segment)
    
    #peak features with dynamic thresholding
    peak_count, peak_height_mean = extract_peak_features(segment, percentile_factor=0.75, prominence_factor=0.1)
    peak_to_peak = np.max(segment) - np.min(segment)
    kurtosis_value = kurtosis(segment)
    skewness_value = skew(segment)
    envelope_mean = np.mean(np.abs(segment))

    #Frequency-Domain Features using dynamic STFT
    stft_spectrum = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length))
    stft_freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)
    spectral_centroid = np.mean(librosa.feature.spectral_centroid(S=stft_spectrum, sr=sample_rate))
    spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(S=stft_spectrum, sr=sample_rate))
   
    psd = stft_spectrum ** 2
    psd_mean = np.mean(psd)
    psd_std = np.std(psd)
    
    #dynamic frequency bands based on Nyquist frequency
    nyquist = sample_rate / 2
    low_cutoff = nyquist * 0.1
    mid_cutoff = nyquist * 0.4
    
    #Low, Mid, High Frequency Bands
    low_band = np.median(psd[stft_freqs < low_cutoff]) if np.any(stft_freqs < low_cutoff) else 0
    mid_band = np.median(psd[(stft_freqs >= low_cutoff) & (stft_freqs < mid_cutoff)]) if np.any((stft_freqs >= low_cutoff) & (stft_freqs < mid_cutoff)) else 0
    high_band = np.median(psd[stft_freqs >= mid_cutoff]) if np.any(stft_freqs >= mid_cutoff) else 0

    psd_norm = psd / np.sum(psd, axis=0, keepdims=True)
    energy_entropy = -np.sum(psd_norm * np.log(psd_norm + 1e-10), axis=0).mean()
    
    return {
        'rms': rms,
        'peak_count': peak_count,
        'peak_height_mean': peak_height_mean,
        'spectral_centroid': spectral_centroid,
        'spectral_bandwidth': spectral_bandwidth,
        'low_band_energy': low_band,
        'mid_band_energy': mid_band,
        'high_band_energy': high_band,
        'peak_to_peak': peak_to_peak,
        'envelope_mean': envelope_mean,
        'skewness_value' : skewness_value,
        'kurtosis_value' : kurtosis_value
    }

def normalize_feature(feature_value, feature_min, feature_max):
    if feature_min == feature_max:
        return 0.5  #neutral value if range is zero
    return (feature_value - feature_min) / (feature_max - feature_min)

def map_feature_to_lra_frequency(feature_value, freq_min=150, freq_max=200):
    return freq_min + feature_value * (freq_max - freq_min)

def map_feature_to_lra_amplitude(feature_value, amp_min=0, amp_max=255):
    return int(amp_min + feature_value * (amp_max - amp_min))

def crossfade(signal, crossfade_duration=0.01):
    fade_length = int(len(signal) * crossfade_duration)
    if fade_length == 0:
        return signal  
    #generate fade-in and fade-out ramps
    fade_in = np.linspace(0, 1, fade_length)
    fade_out = np.linspace(1, 0, fade_length)
    #create crossfaded segment
    crossfaded_segment = signal[-fade_length:] * fade_out + signal[:fade_length] * fade_in
    #construct the new signal by concatenating parts
    crossfaded_signal = np.concatenate((crossfaded_segment, signal[fade_length:-fade_length], crossfaded_segment))

    return crossfaded_signal

def process_segment_features_for_fusion(
    audio_segment,
    accel_segment,
    audio_sample_rate,
    accel_sample_rate,
    global_feature_ranges,
    frequency_feature_from,
    amplitude_feature_from,
    frequency_feature,
    amplitude_feature
):

    #initialize variables
    lra_frequency = None
    lra_amplitude = None

    #process frequency feature
    if frequency_feature_from == "audio":
        audio_features = extract_audio_features_per_segment(audio_segment, audio_sample_rate)
        if audio_features is None:
            print(f"Feature extraction failed for frequency (audio). Segment length: {len(audio_segment)}")
        else:
            normalized_audio_features = {
                key: normalize_feature(
                    audio_features[key],
                    global_feature_ranges[f"{key}_audio"][0],
                    global_feature_ranges[f"{key}_audio"][1],
                )
                for key in audio_features.keys()
            }
            lra_frequency = (
                map_feature_to_lra_frequency(normalized_audio_features.get(frequency_feature))
                if frequency_feature in normalized_audio_features
                else None
            )
    elif frequency_feature_from == "accel":
        accel_features = extract_accel_features_per_segment(accel_segment, accel_sample_rate)
        if accel_features is None:
            print(f"Feature extraction failed for frequency (accel). Segment length: {len(accel_segment)}")
        else:
            normalized_accel_features = {
                key: normalize_feature(
                    accel_features[key],
                    global_feature_ranges[f"{key}_accel"][0],
                    global_feature_ranges[f"{key}_accel"][1],
                )
                for key in accel_features.keys()
            }
            lra_frequency = (
                map_feature_to_lra_frequency(normalized_accel_features.get(frequency_feature))
                if frequency_feature in normalized_accel_features
                else None
            )

    #process amplitude feature
    if amplitude_feature_from == "audio":
        audio_features = extract_audio_features_per_segment(audio_segment, audio_sample_rate)
        if audio_features is None:
            print(f"Feature extraction failed for amplitude (audio). Segment length: {len(audio_segment)}")
        else:
            normalized_audio_features = {
                key: normalize_feature(
                    audio_features[key],
                    global_feature_ranges[f"{key}_audio"][0],
                    global_feature_ranges[f"{key}_audio"][1],
                )
                for key in audio_features.keys()
            }
            lra_amplitude = (
                map_feature_to_lra_amplitude(normalized_audio_features.get(amplitude_feature))
                if amplitude_feature in normalized_audio_features
                else None
            )
    elif amplitude_feature_from == "accel":
        accel_features = extract_accel_features_per_segment(accel_segment, accel_sample_rate)
        if accel_features is None:
            print(f"Feature extraction failed for amplitude (accel). Segment length: {len(accel_segment)}")
        else:
            normalized_accel_features = {
                key: normalize_feature(
                    accel_features[key],
                    global_feature_ranges[f"{key}_accel"][0],
                    global_feature_ranges[f"{key}_accel"][1],
                )
                for key in accel_features.keys()
            }
            lra_amplitude = (
                map_feature_to_lra_amplitude(normalized_accel_features.get(amplitude_feature))
                if amplitude_feature in normalized_accel_features
                else None
            )

    #missing parameters
    if lra_frequency is None:
        print(f"Missing LRA frequency from {frequency_feature_from}. Feature: {frequency_feature}")
    if lra_amplitude is None:
        print(f"Missing LRA amplitude from {amplitude_feature_from}. Feature: {amplitude_feature}")

    return lra_frequency, lra_amplitude

def apply_crossfade(signal, crossfade_fraction):
    signal = np.array(signal)
    total_length = len(signal)
    crossfade_length = int(total_length * crossfade_fraction)
    crossfade_length = min(crossfade_length, total_length // 2)  

    if crossfade_length == 0:
        return signal

    start = signal[:crossfade_length]
    end = signal[-crossfade_length:]
    #crossfade window using a cosine ramp
    t = np.linspace(0, np.pi, crossfade_length, endpoint=False)
    fade_out = 0.5 * (1 + np.cos(t)) 
    fade_in = 0.5 * (1 - np.cos(t))   
    blended = end * fade_out + start * fade_in
    signal[-crossfade_length:] = blended

    return signal

def calculate_crossfade_duration(num_segments, segment_duration, percentage=0.05):
    total_signal_length = num_segments * segment_duration  #total signal length in seconds
    crossfade_duration = total_signal_length * percentage 
    crossfade_segments = int(crossfade_duration / segment_duration)  
    return crossfade_duration, crossfade_segments

def process_and_map_features_over_time(audio_signal, audio_sample_rate, accel_data, accel_sample_rate, global_feature_ranges, window_size_ms=20, overlap=0.5,
                                       use_audio=False, use_accel=False, fusion=False, frequency_feature=None, amplitude_feature=None,
                                       freq_from='audio', amp_from='accel'):

    audio_segments = segment_signal(audio_signal, audio_sample_rate, window_size_ms, overlap)
    accel_segments = segment_signal(accel_data, accel_sample_rate, window_size_ms, overlap)
    print(f"Audio segments: {len(audio_segments)}, Accel segments: {len(accel_segments)}")
    lra_frequencies = []
    lra_amplitudes = []
    audio_features_list = []
    accel_features_list = []
    if use_audio:
        for audio_segment in audio_segments:
            audio_features = extract_audio_features_per_segment(audio_segment, audio_sample_rate)
            audio_features_list.append(audio_features)
            #normalize audio features
            normalized_audio_features = {
                key: normalize_feature(
                    audio_features[key],
                    global_feature_ranges[f'{key}_audio'][0],
                    global_feature_ranges[f'{key}_audio'][1]
                )
                for key in audio_features.keys()
            }
            #map normalized audio features to LRA parameters
            if frequency_feature and frequency_feature in normalized_audio_features:
                lra_frequency = map_feature_to_lra_frequency(normalized_audio_features[frequency_feature])
            else:
                lra_frequency = None

            if amplitude_feature and amplitude_feature in normalized_audio_features:
                lra_amplitude = map_feature_to_lra_amplitude(normalized_audio_features[amplitude_feature])
            else:
                lra_amplitude = None

            #append mapped LRA parameters
            lra_frequencies.append(lra_frequency)
            lra_amplitudes.append(lra_amplitude)
    if use_accel:
            for accel_segment in accel_segments:
                accel_features = extract_accel_features_per_segment(accel_segment, accel_sample_rate)
                accel_features_list.append(accel_features)
                #normalize accelerometer features
                normalized_accel_features = {
                    key: normalize_feature(
                        accel_features[key],
                        global_feature_ranges[f'{key}_accel'][0],
                        global_feature_ranges[f'{key}_accel'][1]
                    )
                    for key in accel_features.keys()
                }
                #map normalized accelerometer features to LRA parameters
                if frequency_feature and frequency_feature in normalized_accel_features:
                    lra_frequency = map_feature_to_lra_frequency(normalized_accel_features[frequency_feature])
                else:
                    lra_frequency = None

                if amplitude_feature and amplitude_feature in normalized_accel_features:
                    lra_amplitude = map_feature_to_lra_amplitude(normalized_accel_features[amplitude_feature])
                else:
                    lra_amplitude = None

                #append mapped LRA parameters
                lra_frequencies.append(lra_frequency)
                lra_amplitudes.append(lra_amplitude)             

    #handle fusion 
    if fusion:
        for i in range(min(len(audio_segments), len(accel_segments))):
            lra_frequency, lra_amplitude = process_segment_features_for_fusion(
                audio_segments[i],
                accel_segments[i],
                audio_sample_rate,
                accel_sample_rate,
                global_feature_ranges,
                freq_from,  
                amp_from,   
                frequency_feature,
                amplitude_feature,
            )

            if lra_frequency is None or lra_amplitude is None:
                print(f"Missing LRA parameters: Freq={lra_frequency}, Amp={lra_amplitude} for segment {i}")
                continue

            lra_frequencies.append(lra_frequency)
            lra_amplitudes.append(lra_amplitude)
            

    #crossfade_fraction = 0.03  #3% of the signal length
    #if len(lra_frequencies) > 0:
       # lra_frequencies = apply_crossfade(lra_frequencies, crossfade_fraction)
        #lra_amplitudes = apply_crossfade(lra_amplitudes, crossfade_fraction)

    return lra_frequencies, lra_amplitudes, audio_features_list, accel_features_list

def segment_signal(signal, sample_rate, window_size_ms=20, overlap=0.5):
    window_size = int(window_size_ms * sample_rate / 1000)  #ms to samples
    step_size = int(window_size * (1 - overlap)) #step size between windows
    segments = []
    for start in range(0, len(signal) - window_size + 1, step_size):
        segment = signal[start:start + window_size]
        if len(segment) > 0: 
            #apply Hanning window 
            hanning_window = np.hanning(len(segment))
            segment = segment * hanning_window
            segments.append(segment)
    return segments

def compute_global_feature_ranges(all_audio_data, all_accel_data, audio_sample_rate, accel_sample_rate, window_size_ms=20, overlap=0.5):
    global_feature_ranges = {
        # Audio features
        'mfcc_mean_audio': [float('inf'), float('-inf')],
        'mfcc_var_audio': [float('inf'), float('-inf')],
        'spectral_centroid_audio': [float('inf'), float('-inf')],
        'spectral_bandwidth_audio': [float('inf'), float('-inf')],
        'spectral_flatness_audio': [float('inf'), float('-inf')],
        'spectral_contrast_audio': [float('inf'), float('-inf')],
        'spectral_rolloff_audio': [float('inf'), float('-inf')],
        'rms_audio': [float('inf'), float('-inf')],
        'zcr_audio': [float('inf'), float('-inf')],
        'onset_strength_mean_audio': [float('inf'), float('-inf')],
        'chroma_mean_audio': [float('inf'), float('-inf')],
        'spectral_flux_audio': [float('inf'), float('-inf')],
        'energy_entropy_audio': [float('inf'), float('-inf')],
        'ste_audio': [float('inf'), float('-inf')],
        'peak_rms_ratio_audio': [float('inf'), float('-inf')],
        'loudness_audio': [float('inf'), float('-inf')],
        'envelope_mean_audio' : [float('inf'), float('-inf')],
        'rms_audio' : [float('inf'), float('-inf')],
        
        # Accel features
        'rms_accel': [float('inf'), float('-inf')],
        'mean_value_accel': [float('inf'), float('-inf')],
        'std_dev_accel': [float('inf'), float('-inf')],
        'peak_count_accel': [float('inf'), float('-inf')],
        'peak_height_mean_accel': [float('inf'), float('-inf')],
        'spectral_centroid_accel': [float('inf'), float('-inf')],
        'spectral_bandwidth_accel': [float('inf'), float('-inf')],
        'psd_mean_accel': [float('inf'), float('-inf')],
        'psd_std_accel': [float('inf'), float('-inf')],
        'low_band_energy_accel': [float('inf'), float('-inf')],
        'mid_band_energy_accel': [float('inf'), float('-inf')],
        'high_band_energy_accel': [float('inf'), float('-inf')],
        'peak_to_peak_accel': [float('inf'), float('-inf')],
        'envelope_mean_accel': [float('inf'), float('-inf')],
        'skewness_value_accel' : [float('inf'), float('-inf')],
        'kurtosis_value_accel' : [float('inf'), float('-inf')]
    }
    #loop through all recordings to compute the global min-max ranges
    for audio_data, accel_data in zip(all_audio_data, all_accel_data):
        #segment the audio and accelerometer signals separately
        audio_segments = segment_signal(audio_data, audio_sample_rate, window_size_ms, overlap)
        accel_segments_y = segment_signal(accel_data, accel_sample_rate, window_size_ms, overlap)
        #process each segment separately for audio and accelerometer
        for audio_segment in audio_segments:
            audio_features = extract_audio_features_per_segment(audio_segment, audio_sample_rate)
            for key in audio_features.keys():
                feature_value = audio_features[key]
                global_feature_ranges[f'{key}_audio'][0] = min(global_feature_ranges[f'{key}_audio'][0], feature_value)
                global_feature_ranges[f'{key}_audio'][1] = max(global_feature_ranges[f'{key}_audio'][1], feature_value)

        for accel_segment_y in accel_segments_y:
            accel_features_y = extract_accel_features_per_segment(accel_segment_y, accel_sample_rate)
            for key in accel_features_y.keys():
                feature_value = accel_features_y[key]
                global_feature_ranges[f'{key}_accel'][0] = min(global_feature_ranges[f'{key}_accel'][0], feature_value)
                global_feature_ranges[f'{key}_accel'][1] = max(global_feature_ranges[f'{key}_accel'][1], feature_value)

    return global_feature_ranges

def concatenate_with_crossfade(segments, crossfade_duration_ms, sample_rate):
    if not segments or len(segments) == 1:
        return np.concatenate(segments) if segments else None, 0
    min_segment_length = min(len(segment) for segment in segments)
    crossfade_length = min(int(sample_rate * crossfade_duration_ms / 1000), min_segment_length // 2)
    if crossfade_length == 0:
        return np.concatenate(segments), 0
    result = segments[0]
    for segment in segments[1:]:
        start = result[-crossfade_length:]
        end = segment[:crossfade_length]
        t = np.linspace(0, np.pi, crossfade_length)
        fade_out = (1 + np.cos(t)) / 2
        fade_in = (1 - np.cos(t)) / 2
        blended = (start * fade_out) + (end * fade_in)
        result = np.concatenate([result[:-crossfade_length], blended, segment[crossfade_length:]])
    return result, crossfade_length

def process_audio_and_accel(audio_signal, accel_signal, loop_count, crossfade_duration_audio_ms, crossfade_duration_accel_ms):
    sample_rate_audio = audio_sample_rate
    sample_rate_accel = accel_sample_rate
    #concatenate audio with crossfade
    audio_repeated = [audio_signal] * loop_count
    concatenated_audio, crossfade_length_audio = concatenate_with_crossfade(audio_repeated, crossfade_duration_audio_ms, sample_rate_audio)
    #concatenate accelerometer data with crossfade
    accel_repeated = [accel_signal] * loop_count
    concatenated_accel, crossfade_length_accel = concatenate_with_crossfade(accel_repeated, crossfade_duration_accel_ms, sample_rate_accel)

    return concatenated_audio, concatenated_accel, crossfade_length_audio, crossfade_length_accel

def plot_waveforms(original_signal, concatenated_signal, sample_rate, title, zoom_range=None):
    time_original = np.linspace(0, len(original_signal) / sample_rate, len(original_signal))
    time_concatenated = np.linspace(0, len(concatenated_signal) / sample_rate, len(concatenated_signal))

    plt.figure(figsize=(14, 6))
    plt.subplot(2, 1, 1)
    plt.plot(time_original, original_signal)
    plt.title(f'Original Signal - {title}')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')

    plt.subplot(2, 1, 2)
    if zoom_range:
        #adjust the time and signal arrays to the zoomed range
        start_sample = int(zoom_range[0] * sample_rate)
        end_sample = int(zoom_range[1] * sample_rate)
        time_concatenated = time_concatenated[start_sample:end_sample]
        concatenated_signal = concatenated_signal[start_sample:end_sample]

    plt.plot(time_concatenated, concatenated_signal)
    plt.title(f'Concatenated Signal with Crossfade - {title}')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')

    plt.tight_layout()
    plt.savefig(f'/mnt/c/Users/annam/Desktop/final/crossfade/{title}.png')
    plt.close()

def check_discontinuity(signal, loop_length, loop_count, crossfade_length):
    discontinuities = []
    for i in range(1, loop_count):
        start_current_loop = i * (loop_length - crossfade_length) #calculate the starting index of the current loop
        end_prev = signal[start_current_loop - crossfade_length:start_current_loop] #get the overlapping region at the end of the previous loop
        start_next = signal[start_current_loop:start_current_loop + crossfade_length] #get the overlapping region at the start of the current loop
        #calculate the difference
        if len(end_prev) == len(start_next):
            diff = np.abs(end_prev - start_next)
            discontinuities.append(np.max(diff))
        else:
            print(f"Warning: Overlapping regions have mismatched lengths for loop {i}.")
            discontinuities.append(None)
    return discontinuities

def check_end_to_start_discontinuity(signal, crossfade_length):
    end = signal[-crossfade_length:]
    start = signal[:crossfade_length]
    diff = np.abs(end - start)
    discontinuity = np.max(diff)
    return discontinuity

def apply_end_to_start_crossfade(signal, crossfade_length):
    if crossfade_length == 0:
        return signal
    start = signal[:crossfade_length]
    end = signal[-crossfade_length:]
    #crossfade window using a cosine ramp 
    t = np.linspace(0, np.pi, crossfade_length, endpoint=False)
    fade_out = 0.5 * (1 + np.cos(t))  #fade out from 1 to 0
    fade_in = 0.5 * (1 - np.cos(t))   #fade in from 0 to 1
    blended = end * fade_out + start * fade_in#blend the end and start segments
    #replace the end and start segments with the blended segment
    signal[:crossfade_length] = blended
    signal[-crossfade_length:] = blended

    return signal

def analyze_discontinuity(signal, discontinuity_value, sample_rate):
    max_signal_value = np.max(np.abs(signal))
    discontinuity_percentage = (discontinuity_value / max_signal_value) * 100 if max_signal_value != 0 else 0
    
    signal_power = np.mean(signal ** 2)
    discontinuity_power = discontinuity_value ** 2
    sdr = 10 * np.log10(signal_power / discontinuity_power) if discontinuity_power != 0 else float('inf')
    
    signal_mean = np.mean(signal)
    signal_std = np.std(signal)
    z_score = (discontinuity_value - signal_mean) / signal_std if signal_std != 0 else 0
    
    print(f"Max Signal Value: {max_signal_value:.2f}")
    print(f"Discontinuity Value: {discontinuity_value:.2f}")
    print(f"Discontinuity Percentage: {discontinuity_percentage:.2f}%")
    print(f"Signal Power: {signal_power:.2f}")
    print(f"Discontinuity Power: {discontinuity_power:.2f}")
    print(f"Signal-to-Discontinuity Ratio (SDR): {sdr:.2f} dB")
    print(f"Discontinuity Z-Score: {z_score:.2f}")

def main():
    #load audio and accelerometer signals
    audio_signals = [librosa.load(audio_path, sr=audio_sample_rate)[0] for audio_path in all_audio_paths]
    accel_signals = [pd.read_csv(accel_path)['Accel_Y'].values for accel_path in all_accel_paths]

    for i, data in enumerate(audio_signals):
        print(f"Audio {i+1} length: {len(data)}")
    for i, data in enumerate(accel_signals):
        print(f"Accel {i+1} length: {len(data)}")

    #concatenate signals
    loop_count = 5  #number of times to repeat the signals
    crossfade_duration_audio_ms = 50   #cossfade duration for audio in milliseconds
    crossfade_duration_accel_ms = 200  #crossfade duration for accelerometer in milliseconds
    concatenated_audio_signals = []
    concatenated_accel_signals = []
    for idx, (audio_signal, accel_signal) in enumerate(zip(audio_signals, accel_signals)):
        concatenated_audio, concatenated_accel, crossfade_length_audio, crossfade_length_accel = process_audio_and_accel(
            audio_signal,
            accel_signal,
            loop_count,
            crossfade_duration_audio_ms,
            crossfade_duration_accel_ms
        )

        print(f"Actual crossfade length for accelerometer {idx+1}: {crossfade_length_accel}")

        # Apply crossfade between end and start of the concatenated signal
        #concatenated_audio = apply_end_to_start_crossfade(concatenated_audio, crossfade_length_audio)
        #concatenated_accel = apply_end_to_start_crossfade(concatenated_accel, crossfade_length_accel)

        print(f"Concatenated audio length: {len(concatenated_audio)}, Concatenated accel length: {len(concatenated_accel)}")
        concatenated_audio_signals.append(concatenated_audio)
        concatenated_accel_signals.append(concatenated_accel)

        # Plot waveforms for each signal
        plot_waveforms(audio_signal, concatenated_audio, audio_sample_rate, f'Audio_{idx+1}')
        plot_waveforms(accel_signal, concatenated_accel, accel_sample_rate, f'Accelerometer_{idx+1}')

        # Check discontinuities for audio
        loop_length_audio = len(audio_signal)
        discontinuities_audio = check_discontinuity(concatenated_audio, loop_length_audio, loop_count, crossfade_length_audio)
        print(f"Discontinuities at loop points audio: {discontinuities_audio}")

        # Check discontinuities for accelerometer
        loop_length_accel = len(accel_signal)
        discontinuities_accel = check_discontinuity(concatenated_accel, loop_length_accel, loop_count, crossfade_length_accel)
        print(f"Discontinuities at loop points accel: {discontinuities_accel}")

        for idx, discontinuity_value in enumerate(discontinuities_accel):
            print(f"Analyzing discontinuity at loop point {idx+1}:")
            analyze_discontinuity(concatenated_accel, discontinuity_value, accel_sample_rate)

        # Check discontinuity between end and start after applying the crossfade
        discontinuity_audio_end = check_end_to_start_discontinuity(concatenated_audio, crossfade_length_audio)
        print(f"Discontinuity between end and start of audio: {discontinuity_audio_end}")

        discontinuity_acc_end = check_end_to_start_discontinuity(concatenated_accel, crossfade_length_accel)
        print(f"Discontinuity between end and start of accel: {discontinuity_acc_end}")

    #compute global feature ranges
    global_feature_ranges = compute_global_feature_ranges(concatenated_audio_signals, concatenated_accel_signals, audio_sample_rate, accel_sample_rate)
    print("Global Feature Ranges: ", global_feature_ranges)

    feature_tests = [
        {
            "test_type": "audio_only",
            "freq_from": "audio",
            "amp_from": "audio",
            "features_to_test": [
                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'spectral_rolloff', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'spectral_flux', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'spectral_contrast', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'mfcc_mean', 'amplitude_feature': 'peak_rms_ratio'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'spectral_rolloff', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'spectral_flux', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'spectral_contrast', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'mfcc_mean', 'amplitude_feature': 'mfcc_var'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_rolloff', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_flux', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_contrast', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'mfcc_mean', 'amplitude_feature': 'rms'},
            ]
        },
        {
            "test_type": "accel_only",
            "freq_from": "accel",
            "amp_from": "accel",
            "features_to_test": [
                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'rms'},
                    
                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'envelope_mean'},
                    
                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'peak_to_peak'},


                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'kurtosis_value'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'kurtosis_value'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'kurtosis_value'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'kurtosis_value'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'kurtosis_value'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'skewness_value'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'skewness_value'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'skewness_value'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'skewness_value'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'skewness_value'}
                
            ]
        },
        {
            "test_type": "audio_freq_accel_amp",
            "freq_from": "audio",
            "amp_from": "accel",
            "features_to_test": [
                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_rolloff', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_flux', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_contrast', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'mfcc_mean', 'amplitude_feature': 'rms'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'spectral_rolloff', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'spectral_flux', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'spectral_contrast', 'amplitude_feature': 'envelope_mean'},
                {'frequency_feature': 'mfcc_mean', 'amplitude_feature': 'envelope_mean'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'spectral_rolloff', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'spectral_flux', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'spectral_contrast', 'amplitude_feature': 'peak_to_peak'},
                {'frequency_feature': 'mfcc_mean', 'amplitude_feature': 'peak_to_peak'},
            ]
        },

         {
            "test_type": "accel_freq_audio_amp",
            "freq_from": "accel",
            "amp_from": "audio",
            "features_to_test": [
                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'peak_rms_ratio'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'peak_rms_ratio'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'mfcc_var'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'mfcc_var'},

                {'frequency_feature': 'spectral_centroid', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'spectral_bandwidth', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'low_band_energy', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'mid_band_energy', 'amplitude_feature': 'rms'},
                {'frequency_feature': 'high_band_energy', 'amplitude_feature': 'rms'},
            ]
        }
    ]

    for i, (audio_signal, accel_signal) in enumerate(zip(concatenated_audio_signals, concatenated_accel_signals)):
        base_filename = os.path.splitext(os.path.basename(all_audio_paths[i]))[0]
        for feature_test in feature_tests:
            test_type = feature_test["test_type"]
            freq_from = feature_test["freq_from"]
            amp_from = feature_test["amp_from"]
            for feature_set in feature_test["features_to_test"]:
                test_name = f"{test_type}_{feature_set['frequency_feature']}_{feature_set['amplitude_feature']}"
                use_audio = (freq_from == "audio" and amp_from == "audio") 
                use_accel = (freq_from == "accel" and amp_from == "accel") 
                fusion = freq_from != amp_from
                try:
                    process_test_case(
                        audio_signal,
                        audio_sample_rate,
                        accel_signal,
                        accel_sample_rate,
                        global_feature_ranges,
                        feature_set,
                        base_filename,
                        test_name,
                        use_audio=use_audio,
                        use_accel=use_accel,
                        fusion=fusion,
                        freq_from=freq_from,
                        amp_from=amp_from
                    )
                except Exception as e:
                    print(f"Error in test {test_name}: {e}")

def process_test_case(audio_data, audio_sample_rate, accel_data, accel_sample_rate, global_feature_ranges, feature_set, base_filename, test_name, use_audio, 
                      use_accel, fusion, freq_from, amp_from):

    lra_frequencies, lra_amplitudes, audio_features, accel_features = process_and_map_features_over_time(
        audio_data,
        audio_sample_rate,
        accel_data,
        accel_sample_rate,
        global_feature_ranges,
        window_size_ms=20,
        overlap=0.5,
        use_audio=use_audio,
        use_accel=use_accel,
        fusion=fusion,
        frequency_feature=feature_set['frequency_feature'],
        amplitude_feature=feature_set['amplitude_feature'],
        freq_from=freq_from,
        amp_from=amp_from
    )

    #save LRA data to CSV
    output_csv_path = f'/mnt/c/Users/annam/Desktop/final/final/{base_filename}_{test_name}.csv'
    lra_data = pd.DataFrame({'Frequency': lra_frequencies, 'Amplitude': lra_amplitudes})
    lra_data.to_csv(output_csv_path, index=False)

    #generate combined waveform plot
    signal_sampling_rate = audio_sample_rate if freq_from == "audio" else accel_sample_rate
    generate_combined_waveform_plot(lra_frequencies, lra_amplitudes, base_filename, test_name, signal_sampling_rate)

    #generate feature plot
    plot_output_path = f'/mnt/c/Users/annam/Desktop/final/output_plots/{base_filename}_{test_name}_lra_plot.png'
    plot_features_and_lra(lra_frequencies, lra_amplitudes, audio_features, accel_features, 20, 0.5, audio_sample_rate, plot_output_path)

def generate_combined_waveform_plot(frequencies, amplitudes, base_filename, test_name, sampling_rate):
 
    duration_per_wave = 0.1  #duration of each sine wave (in seconds)
    combined_waveform = []

    for frequency, amplitude in zip(frequencies, amplitudes):
        t = np.linspace(0, duration_per_wave, int(sampling_rate * duration_per_wave), endpoint=False)
        sine_wave = amplitude * np.sin(2 * np.pi * frequency * t)
        combined_waveform.extend(sine_wave)  #append each sine wave to the combined waveform

    combined_waveform = np.array(combined_waveform)
    plot_path = f'/mnt/c/Users/annam/Desktop/final/output_plots/waveforms/{base_filename}_{test_name}_combined_waveform.png'
    time = np.linspace(0, len(combined_waveform) / sampling_rate, len(combined_waveform), endpoint=False)
    plt.figure(figsize=(14, 6))
    plt.plot(time, combined_waveform, label="Combined Waveform")
    plt.title(f"Combined Sine Waveform for Frequency-Amplitude Pairs (Sampling Rate: {sampling_rate} Hz)")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

def plot_features_and_lra(lra_frequencies, lra_amplitudes, audio_features_list, accel_features_list, window_size_ms, overlap, sample_rate, output_path):
    time_per_segment = window_size_ms / 1000 * overlap
    times = [i * time_per_segment for i in range(len(lra_frequencies))]
    
    plt.figure(figsize=(14, 10))
    
    #plot LRA frequency over time
    plt.subplot(3, 1, 1)
    plt.plot(lra_frequencies, label='LRA Frequency', color='blue')
    plt.xlabel('Time (s)')
    plt.ylabel('Frequency (Hz)')
    plt.title('LRA Frequency Over Time')
    plt.legend()
    plt.grid(True)
    
    #plot LRA amplitude over time
    plt.subplot(3, 1, 2)
    plt.plot(lra_amplitudes, label='LRA Amplitude', color='green')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.title('LRA Amplitude Over Time')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    
if __name__ == "__main__":
    main()  