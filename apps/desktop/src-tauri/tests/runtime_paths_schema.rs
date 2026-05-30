#[test]
fn runtime_paths_schema_fixture_names_are_frozen() {
    let fixtures = [
        "../../../tests/fixtures/runtime_paths/windows_dev.json",
        "../../../tests/fixtures/runtime_paths/windows_release.json",
        "../../../tests/fixtures/runtime_paths/invalid_repo_release.json",
    ];
    for fixture in fixtures {
        assert!(std::path::Path::new(fixture).exists(), "{fixture} missing");
    }
}
