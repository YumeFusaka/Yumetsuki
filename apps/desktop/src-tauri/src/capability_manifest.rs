use std::collections::{BTreeMap, BTreeSet};

use crate::command_catalog::{PET_ALLOWED_COMMANDS, REGISTERED_COMMANDS, SECURITY_CLASSIFIED_COMMANDS};

pub fn registered_commands() -> BTreeSet<&'static str> {
    REGISTERED_COMMANDS.iter().copied().collect()
}

pub fn security_classes() -> BTreeMap<&'static str, &'static str> {
    SECURITY_CLASSIFIED_COMMANDS.iter().copied().collect()
}

pub fn commands_missing_security_class() -> Vec<&'static str> {
    let classes = security_classes();
    REGISTERED_COMMANDS
        .iter()
        .copied()
        .filter(|command| !classes.contains_key(command))
        .collect()
}

pub fn pet_allowed_commands() -> BTreeSet<&'static str> {
    PET_ALLOWED_COMMANDS.iter().copied().collect()
}

pub fn dangerous_permission_prefixes() -> &'static [&'static str] {
    &["shell:", "fs:", "opener:", "http:", "clipboard:"]
}
