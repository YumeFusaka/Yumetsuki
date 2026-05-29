use yumetsuki_desktop::audio::{AudioFormat, PcmStreamPlayback, StreamingAudioBuffer, WavPlaybackBuffer};
use yumetsuki_desktop::recorder::{build_wav, is_pcm16_silent, RecorderConfig, RecorderState};

#[test]
fn streaming_audio_buffer_reads_appended_bytes_in_order_and_compacts_prefix() {
    let mut buffer = StreamingAudioBuffer::default();

    buffer.append(b"ab");
    buffer.append(b"cd");
    assert_eq!(buffer.read(3), b"abc");

    buffer.append(&vec![b'x'; 8192]);
    let before = buffer.offset();
    let _ = buffer.read(4096);
    buffer.append(b"yz");

    assert!(buffer.offset() < before + 4096);
    assert!(buffer.available() > 0);
}

#[test]
fn pcm_and_wav_playback_contracts_are_deterministic() {
    let format = AudioFormat {
        transport: "pcm_stream".to_string(),
        sample_rate: 32_000,
        channels: 1,
        sample_width: 2,
    };
    let mut pcm = PcmStreamPlayback::new(format.clone());
    assert!(!pcm.has_started_playback());

    pcm.append_chunk(b"\x00\x01");
    assert!(pcm.has_started_playback());
    assert_eq!(pcm.format(), &format);

    let mut wav = WavPlaybackBuffer::default();
    wav.append_chunk(b"a");
    wav.append_chunk(b"b");
    assert!(!wav.finished());

    wav.finish();
    assert!(wav.finished());
    assert_eq!(wav.payload(), b"ab");
}

#[test]
fn recorder_config_clamps_runtime_settings() {
    let config = RecorderConfig::new(1, 0.0, 10, -1);

    assert_eq!(config.record_timeout_seconds, 3);
    assert_eq!(config.silence_threshold, 0.001);
    assert_eq!(config.silence_duration_ms, 300);
    assert_eq!(config.initial_silence_grace_ms, 0);
}

#[test]
fn recorder_pcm16_silence_detection_and_wav_builder_match_runtime_contract() {
    let loud = [1200_i16; 8]
        .iter()
        .flat_map(|sample| sample.to_le_bytes())
        .collect::<Vec<_>>();
    let silent = [0_i16; 8]
        .iter()
        .flat_map(|sample| sample.to_le_bytes())
        .collect::<Vec<_>>();

    assert!(is_pcm16_silent(&silent, 0.02));
    assert!(!is_pcm16_silent(&loud, 0.02));
    assert!(is_pcm16_silent(&[0, 0, 255], 0.02));

    let wav = build_wav(&loud, 16_000, 1, 2);
    assert_eq!(&wav[0..4], b"RIFF");
    assert_eq!(&wav[8..12], b"WAVE");
    assert_eq!(u32::from_le_bytes(wav[24..28].try_into().unwrap()), 16_000);
    assert_eq!(u16::from_le_bytes(wav[22..24].try_into().unwrap()), 1);
    assert_eq!(u16::from_le_bytes(wav[34..36].try_into().unwrap()), 16);
    assert_eq!(&wav[wav.len() - loud.len()..], loud.as_slice());
}

#[test]
fn recorder_start_stop_cancel_are_idempotent_and_release_runtime_state() {
    let mut recorder = RecorderState::new(RecorderConfig::default());

    recorder.start();
    recorder.start();
    recorder.push_chunk(b"\x01\x00\x02\x00");

    let wav = recorder.stop().expect("stop 应返回 WAV 音频");
    assert_eq!(recorder.start_count(), 1);
    assert_eq!(recorder.stop_count(), 1);
    assert!(!recorder.is_recording());
    assert!(wav.starts_with(b"RIFF"));

    assert!(recorder.stop().is_none());
    recorder.start();
    recorder.push_chunk(b"\x64\x00");
    recorder.cancel();
    recorder.cancel();

    assert_eq!(recorder.cancel_count(), 1);
    assert!(!recorder.is_recording());
    assert!(recorder.buffer_is_empty());
}
