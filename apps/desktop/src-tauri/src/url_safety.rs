use std::net::{IpAddr, Ipv4Addr};

pub fn normalize_url(input: &str) -> Result<String, String> {
    let trimmed = input.trim();
    let lower = trimmed.to_ascii_lowercase();
    if lower.starts_with("file://") {
        return Err("security.permission_denied".to_string());
    }
    if !(lower.starts_with("http://") || lower.starts_with("https://")) {
        return Err("security.permission_denied".to_string());
    }
    if host_part(trimmed).is_none() {
        return Err("security.permission_denied".to_string());
    }
    Ok(trimmed.to_string())
}

pub fn needs_confirmation(input: &str) -> Result<bool, String> {
    let normalized = normalize_url(input)?;
    let host = host_part(&normalized).ok_or_else(|| "security.permission_denied".to_string())?;
    if is_local_or_private_host(host) {
        return Ok(true);
    }
    Ok(false)
}

fn host_part(input: &str) -> Option<&str> {
    let after_scheme = input.split_once("://")?.1;
    let authority = after_scheme.split('/').next().unwrap_or(after_scheme);
    let host = authority.split('@').last().unwrap_or(authority);
    let host = host.split(':').next().unwrap_or(host);
    if host.is_empty() {
        None
    } else {
        Some(host)
    }
}

fn is_local_or_private_host(host: &str) -> bool {
    let lower = host.to_ascii_lowercase();
    if matches!(lower.as_str(), "localhost" | "127.0.0.1" | "::1") || lower.ends_with(".localhost") {
        return true;
    }
    match lower.parse::<IpAddr>() {
        Ok(IpAddr::V4(ip)) => is_private_ipv4(ip),
        Ok(IpAddr::V6(ip)) => ip.is_loopback() || ip.is_unique_local(),
        Err(_) => false,
    }
}

fn is_private_ipv4(ip: Ipv4Addr) -> bool {
    ip.is_private() || ip.is_loopback() || ip.is_link_local()
}
