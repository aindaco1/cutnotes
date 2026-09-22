import array
import copy
import math
from pathlib import Path
import tempfile
import unittest
import wave

from cutnotes_core.speech_levels import analyze_speech_levels
from cutnotes_core.transcription import EVIDENCE_SCHEMA, audio_digest, text_digest


class SpeechLevelTests(unittest.TestCase):
    def fixture(self, root, levels):
        rate, samples, words = 16000, array.array("h"), []
        for group, amplitudes in enumerate(levels):
            samples.extend([0] * rate)
            for index, amplitude in enumerate(amplitudes):
                start = len(samples) / rate
                samples.extend(int(amplitude * 32767 * math.sin(2 * math.pi * 220 * i / rate))
                               for i in range(rate // 5))
                words.append({"text": f"group{group}word{index}", "start": start, "end": len(samples) / rate})
        path = root / "voice.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(rate)
            audio.writeframes(samples.tobytes())
        transcript = " ".join(w["text"] for w in words) + "\n"
        evidence = {"schema_version": EVIDENCE_SCHEMA, "transcript_sha256": text_digest(transcript),
                    "audio_sha256": audio_digest(path), "duration_seconds": len(samples) / rate, "words": words}
        return dict(transcript=transcript, evidence=evidence, source_audio=path, pcm_audio=path)

    def test_sustained_quiet_utterance_is_a_reviewable_background_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory), [[.2] * 5, [.004] * 5, [.18] * 5])
            original = args["source_audio"].read_bytes()
            report = analyze_speech_levels(**args)
            self.assertEqual([r["background_candidate"] for r in report["utterances"]], [False, True, False])
            self.assertNotIn("group1", report["proposed_foreground_transcript"])
            self.assertIn("group0word4", report["proposed_foreground_transcript"])
            self.assertIn("group2word0", report["proposed_foreground_transcript"])
            self.assertTrue(report["requires_review"])
            self.assertEqual(args["source_audio"].read_bytes(), original)

    def test_a_quiet_speaker_is_not_removed_by_an_absolute_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory), [[.003] * 5, [.002] * 5, [.0025] * 5])
            report = analyze_speech_levels(**args)
            self.assertFalse(any(r["background_candidate"] for r in report["utterances"]))
            self.assertEqual(report["proposed_foreground_transcript"], args["transcript"])

    def test_soft_word_endings_stay_with_the_utterance(self):
        for opening in ([.2, .2, .2, .002, .002], [.2, .002, .002]):
            with self.subTest(opening=opening), tempfile.TemporaryDirectory() as directory:
                args = self.fixture(Path(directory), [opening, [.2] * 5, [.2] * 5])
                report = analyze_speech_levels(**args)
                self.assertEqual(report["proposed_foreground_transcript"], args["transcript"])

    def test_short_recording_does_not_establish_a_background_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory), [[.2] * 5, [.002] * 5])
            report = analyze_speech_levels(**args)
            self.assertFalse(any(r["background_candidate"] for r in report["utterances"]))

    def test_normal_changes_in_speaking_level_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory), [[.2] * 5, [.07] * 5, [.12] * 5])
            self.assertEqual(analyze_speech_levels(**args)["proposed_foreground_transcript"], args["transcript"])

    def test_relative_proposals_are_stable_across_twelve_gain_variants(self):
        # Synthetic tones test measurement invariance, not speaker recognition.
        for background in (.002, .004, .01):
            for gain in (.1, .25, .5, 1):
                with self.subTest(background=background, gain=gain), tempfile.TemporaryDirectory() as directory:
                    levels = [[.2 * gain] * 5, [background * gain] * 5, [.18 * gain] * 5]
                    report = analyze_speech_levels(**self.fixture(Path(directory), levels))
                    self.assertEqual([r["background_candidate"] for r in report["utterances"]], [False, True, False])

    def test_compressed_and_equal_level_background_cannot_be_identified_by_volume(self):
        for background in (.08, .2):
            with self.subTest(background=background), tempfile.TemporaryDirectory() as directory:
                args = self.fixture(Path(directory), [[.2] * 5, [background] * 5, [.2] * 5])
                self.assertEqual(analyze_speech_levels(**args)["proposed_foreground_transcript"], args["transcript"])

    def test_a_deliberate_whisper_remains_an_unresolved_review_proposal(self):
        # A user's whisper and distant speech can have the same level evidence.
        # Never describe this measurement as a validated deletion or speaker ID.
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory), [[.2] * 5, [.004] * 5, [.2] * 5])
            report = analyze_speech_levels(**args)
            self.assertTrue(report["utterances"][1]["background_candidate"])
            self.assertTrue(report["requires_review"])
            self.assertIn("group1word0", report["utterances"][1]["text"])

    def test_mismatched_or_incomplete_alignment_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory), [[.2] * 5] * 3)
            mutations = [lambda e: e.update(transcript_sha256="wrong"),
                         lambda e: e.update(audio_sha256="wrong"),
                         lambda e: e["words"].pop(),
                         lambda e: e["words"][0].update(start=float("nan")),
                         lambda e: e.update(duration_seconds=True)]
            for mutate in mutations:
                bad = copy.deepcopy(args["evidence"])
                mutate(bad)
                with self.assertRaises(ValueError):
                    analyze_speech_levels(**dict(args, evidence=bad))


if __name__ == "__main__":
    unittest.main()
