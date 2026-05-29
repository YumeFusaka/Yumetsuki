#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AudioFormat {
    pub transport: String,
    pub sample_rate: u32,
    pub channels: u16,
    pub sample_width: u16,
}

#[derive(Debug, Default, Clone)]
pub struct StreamingAudioBuffer {
    chunks: Vec<u8>,
    offset: usize,
    finished: bool,
}

impl StreamingAudioBuffer {
    const COMPACT_THRESHOLD: usize = 4096;

    pub fn append(&mut self, data: &[u8]) {
        if data.is_empty() {
            return;
        }
        self.compact_if_needed();
        self.chunks.extend_from_slice(data);
    }

    pub fn finish(&mut self) {
        self.finished = true;
    }

    pub fn read(&mut self, max_len: usize) -> Vec<u8> {
        if max_len == 0 || self.offset >= self.chunks.len() {
            return Vec::new();
        }
        let end = self.chunks.len().min(self.offset + max_len);
        let data = self.chunks[self.offset..end].to_vec();
        self.offset = end;
        self.compact_if_needed();
        data
    }

    pub fn available(&self) -> usize {
        self.chunks.len().saturating_sub(self.offset)
    }

    pub fn has_pending_data(&self) -> bool {
        self.offset < self.chunks.len()
    }

    pub fn at_end(&self) -> bool {
        self.finished && !self.has_pending_data()
    }

    pub fn offset(&self) -> usize {
        self.offset
    }

    fn compact_if_needed(&mut self) {
        if self.offset < Self::COMPACT_THRESHOLD {
            return;
        }
        self.chunks.drain(..self.offset);
        self.offset = 0;
    }
}

#[derive(Debug, Clone)]
pub struct PcmStreamPlayback {
    format: AudioFormat,
    has_started_playback: bool,
    finish_requested: bool,
    buffer: StreamingAudioBuffer,
}

impl PcmStreamPlayback {
    pub fn new(format: AudioFormat) -> Self {
        Self {
            format,
            has_started_playback: false,
            finish_requested: false,
            buffer: StreamingAudioBuffer::default(),
        }
    }

    pub fn append_chunk(&mut self, data: &[u8]) {
        self.buffer.append(data);
        if !data.is_empty() {
            self.has_started_playback = true;
        }
    }

    pub fn finish(&mut self) {
        self.finish_requested = true;
        self.buffer.finish();
    }

    pub fn has_started_playback(&self) -> bool {
        self.has_started_playback
    }

    pub fn finish_requested(&self) -> bool {
        self.finish_requested
    }

    pub fn format(&self) -> &AudioFormat {
        &self.format
    }
}

#[derive(Debug, Default)]
pub struct WavPlaybackBuffer {
    payload: Vec<u8>,
    finished: bool,
}

impl WavPlaybackBuffer {
    pub fn append_chunk(&mut self, data: &[u8]) {
        self.payload.extend_from_slice(data);
    }

    pub fn finish(&mut self) {
        self.finished = true;
    }

    pub fn finished(&self) -> bool {
        self.finished
    }

    pub fn payload(&self) -> &[u8] {
        &self.payload
    }
}
