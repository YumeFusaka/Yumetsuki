#[derive(Debug, Clone, PartialEq)]
pub struct RecorderConfig {
    pub record_timeout_seconds: u32,
    pub silence_threshold: f32,
    pub silence_duration_ms: u32,
    pub initial_silence_grace_ms: u32,
}

impl Default for RecorderConfig {
    fn default() -> Self {
        Self::new(20, 0.02, 1200, 3000)
    }
}

impl RecorderConfig {
    pub fn new(
        record_timeout_seconds: i32,
        silence_threshold: f32,
        silence_duration_ms: i32,
        initial_silence_grace_ms: i32,
    ) -> Self {
        Self {
            record_timeout_seconds: record_timeout_seconds.max(3) as u32,
            silence_threshold: silence_threshold.max(0.001),
            silence_duration_ms: silence_duration_ms.max(300) as u32,
            initial_silence_grace_ms: initial_silence_grace_ms.max(0) as u32,
        }
    }
}

#[derive(Debug, Clone)]
pub struct RecorderState {
    config: RecorderConfig,
    recording: bool,
    stopping: bool,
    buffer: Vec<u8>,
    start_count: u32,
    stop_count: u32,
    cancel_count: u32,
}

impl RecorderState {
    pub fn new(config: RecorderConfig) -> Self {
        Self {
            config,
            recording: false,
            stopping: false,
            buffer: Vec::new(),
            start_count: 0,
            stop_count: 0,
            cancel_count: 0,
        }
    }

    pub fn start(&mut self) {
        if self.recording {
            return;
        }
        self.recording = true;
        self.stopping = false;
        self.buffer.clear();
        self.start_count += 1;
    }

    pub fn push_chunk(&mut self, chunk: &[u8]) {
        if self.recording && !chunk.is_empty() {
            self.buffer.extend_from_slice(chunk);
        }
    }

    pub fn stop(&mut self) -> Option<Vec<u8>> {
        if !self.recording || self.stopping {
            return None;
        }
        self.stopping = true;
        self.stop_count += 1;
        self.recording = false;
        let pcm = std::mem::take(&mut self.buffer);
        self.stopping = false;
        Some(build_wav(&pcm, 16_000, 1, 2))
    }

    pub fn cancel(&mut self) {
        if !self.recording && self.buffer.is_empty() {
            return;
        }
        self.recording = false;
        self.stopping = false;
        self.buffer.clear();
        self.cancel_count += 1;
    }

    pub fn is_recording(&self) -> bool {
        self.recording
    }

    pub fn buffer_is_empty(&self) -> bool {
        self.buffer.is_empty()
    }

    pub fn start_count(&self) -> u32 {
        self.start_count
    }

    pub fn stop_count(&self) -> u32 {
        self.stop_count
    }

    pub fn cancel_count(&self) -> u32 {
        self.cancel_count
    }

    pub fn config(&self) -> &RecorderConfig {
        &self.config
    }
}

pub fn is_pcm16_silent(pcm: &[u8], threshold: f32) -> bool {
    let sample_count = pcm.len() / 2;
    if sample_count == 0 {
        return true;
    }

    let usable = sample_count * 2;
    let mut total = 0_f64;
    for chunk in pcm[..usable].chunks_exact(2) {
        let sample = i16::from_le_bytes([chunk[0], chunk[1]]) as f64;
        total += sample * sample;
    }
    let rms = (total / sample_count as f64).sqrt() / 32768.0;
    rms < threshold.max(0.001) as f64
}

pub fn build_wav(pcm: &[u8], sample_rate: u32, channels: u16, sample_width: u16) -> Vec<u8> {
    let bits_per_sample = sample_width.saturating_mul(8);
    let byte_rate = sample_rate
        .saturating_mul(channels as u32)
        .saturating_mul(sample_width as u32);
    let block_align = channels.saturating_mul(sample_width);
    let data_len = pcm.len() as u32;
    let riff_len = 36_u32.saturating_add(data_len);

    let mut out = Vec::with_capacity(44 + pcm.len());
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&riff_len.to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16_u32.to_le_bytes());
    out.extend_from_slice(&1_u16.to_le_bytes());
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&byte_rate.to_le_bytes());
    out.extend_from_slice(&block_align.to_le_bytes());
    out.extend_from_slice(&bits_per_sample.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    out.extend_from_slice(pcm);
    out
}
