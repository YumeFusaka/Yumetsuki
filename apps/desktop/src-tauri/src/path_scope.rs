use std::path::{Path, PathBuf};

use crate::runtime_paths::{assert_in_scope, RuntimePathError};

#[derive(Debug, Clone)]
pub struct PathScope {
    allowed_roots: Vec<PathBuf>,
}

impl PathScope {
    pub fn new<I, P>(allowed_roots: I) -> Self
    where
        I: IntoIterator<Item = P>,
        P: Into<PathBuf>,
    {
        Self {
            allowed_roots: allowed_roots.into_iter().map(Into::into).collect(),
        }
    }

    pub fn assert_allowed(&self, path: impl AsRef<Path>) -> Result<PathBuf, RuntimePathError> {
        let roots = self.allowed_roots.iter().map(PathBuf::as_path).collect::<Vec<_>>();
        assert_in_scope(path.as_ref(), &roots)
    }

    pub fn resolve_child(&self, root: &Path, filename: &str) -> Result<PathBuf, RuntimePathError> {
        validate_safe_filename(filename)?;
        self.assert_allowed(root.join(filename))
    }
}

pub fn validate_safe_filename(filename: &str) -> Result<(), RuntimePathError> {
    if filename.is_empty()
        || filename == "."
        || filename == ".."
        || filename.contains('/')
        || filename.contains('\\')
        || filename.contains(':')
    {
        return Err(RuntimePathError::OutOfScope(filename.to_string()));
    }

    let valid = filename
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.'));
    if valid {
        Ok(())
    } else {
        Err(RuntimePathError::OutOfScope(filename.to_string()))
    }
}
