# Third-Party Notices

CutNotes source code is MIT-licensed. Release builds aggregate the components below under their own licenses. Full license texts are copied into `CutNotes.app/Contents/Resources/Licenses/` by the release build.

| Component | Pinned version | License | Purpose |
|---|---:|---|---|
| Python | 3.14.6 | PSF License | Bundled CLI interpreter |
| FFmpeg / FFprobe | 8.1.1 | LGPL 2.1 or later | Recording, media probing, decoding, and chunking |
| Record | 1.2.2 | MIT | Reusable local speech interface |
| FluidAudio | 0.15.6 | Apache 2.0 | Core ML Parakeet inference |
| Swift Argument Parser | 1.8.2 | Apache 2.0 | Transitive Record package dependency |
| Sparkle | 2.9.6 | MIT plus bundled external notices | Signed app updates |
| OpenSSL | 3.6.3 | Apache 2.0 | Python HTTPS support |
| XZ Utils | runtime-resolved | 0BSD/LGPL/GPL files as applicable | Python compression support |
| mpdecimal | 4.0.1 | BSD-2-Clause | Python decimal arithmetic |
| SQLite | runtime-resolved | Public domain | Python database module |
| Zstandard | runtime-resolved | BSD-3-Clause/GPL dual license | Python compression support |

The CutNotes FFmpeg build is compiled from the pinned upstream 8.1.1 source with external codec autodetection disabled and without `--enable-gpl` or `--enable-nonfree`. Its configuration and version are checked during packaging.

## Optional and separately installed tools

MacWhisper and Codex CLI are not distributed with CutNotes. Their licenses, services, and data handling apply only when a user selects those providers.

## Parakeet model

The model weights are not included in the app or DMG. After explicit user acceptance, CutNotes downloads the exact Core ML conversion from `FluidInference/parakeet-tdt-0.6b-v3-coreml` at revision `aed02740059203c4a87495924f685de3722ae9ce` and verifies a pinned SHA-256 manifest.

- Original model: NVIDIA Parakeet-TDT-0.6B-v3
- Original model page: <https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3>
- Core ML source: <https://huggingface.co/FluidInference/parakeet-tdt-0.6b-v3-coreml>
- License: Creative Commons Attribution 4.0 International
- License text: <https://creativecommons.org/licenses/by/4.0/legalcode>

An attribution file is installed beside the downloaded model.
