from pathlib import Path
import re

ROOT = Path("source/Sawtiyat-0.7.14-source")


def read(path: str):
    p = ROOT / path
    return p, p.read_text(encoding="utf-8")


def write(p, s):
    p.write_text(s, encoding="utf-8")


def replace_required(path: str, old: str, new: str):
    p, s = read(path)
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"Expected one match in {path}, found {n}: {old[:100]!r}")
    write(p, s.replace(old, new, 1))


def replace_optional(path: str, old: str, new: str):
    p, s = read(path)
    if old in s:
        write(p, s.replace(old, new, 1))


def regex_required(path: str, pattern: str, replacement: str):
    p, s = read(path)
    s, n = re.subn(pattern, replacement, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"Expected one regex match in {path}, found {n}: {pattern}")
    write(p, s)


def regex_optional(path: str, pattern: str, replacement: str):
    p, s = read(path)
    s, n = re.subn(pattern, replacement, s, count=1, flags=re.S)
    if n:
        write(p, s)


# Version identity.
p, s = read("app/build.gradle.kts")
s, n1 = re.subn(r'versionCode\s*=\s*\d+', 'versionCode = 38', s, count=1)
s, n2 = re.subn(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.7.22"', s, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit("Could not update Android versionCode/versionName")
write(p, s)

src = "app/src/main/java/com/sawtiyat/app/audio/OfflineArabicSpeech.kt"
replace_required(src,
'''            paragraphEnd -> (style.pauseMs * 0.7f).toLong().coerceIn(250L, 380L)
            text.trimEnd().endsWith("؟") || text.trimEnd().endsWith("?") || text.trimEnd().endsWith("!") ||
                text.trimEnd().endsWith(".") || text.trimEnd().endsWith("۔") -> 260L
            text.trimEnd().endsWith("؛") || text.trimEnd().endsWith(";") || text.trimEnd().endsWith(":") -> 180L
            text.trimEnd().endsWith("،") || text.trimEnd().endsWith(",") -> 120L
''',
'''            paragraphEnd -> (style.pauseMs * 0.45f).toLong().coerceIn(160L, 240L)
            text.trimEnd().endsWith("؟") || text.trimEnd().endsWith("?") || text.trimEnd().endsWith("!") ||
                text.trimEnd().endsWith(".") || text.trimEnd().endsWith("۔") -> 220L
            text.trimEnd().endsWith("؛") || text.trimEnd().endsWith(";") || text.trimEnd().endsWith(":") -> 150L
            text.trimEnd().endsWith("،") || text.trimEnd().endsWith(",") -> 90L
''')
replace_required(src,
'''    /** يحافظ Supertonic على معامل الصمت المحدد لكل نمط كما في 0.7.9. */
    internal fun effectiveSupertonicSilenceScale(style: Style): Float = style.silenceScale
''',
'''    /** Supertonic expects seconds between its internal chunks, not a silenceScale multiplier. */
    internal fun effectiveSupertonicSilenceDuration(style: Style): Float = when (style) {
        Style.NEWS -> 0.12f
        Style.MEDIA -> 0.15f
        Style.BOOK -> 0.18f
        Style.NARRATOR -> 0.20f
        Style.DOCUMENTARY -> 0.22f
    }

    /** Native option names supported by Sherpa-ONNX 2.0.1 Supertonic. */
    internal fun supertonicExtraOptions(style: Style, seed: Int): Map<String, String> = mapOf(
        "lang" to "ar",
        "seed" to seed.toString(),
        "silence_duration" to effectiveSupertonicSilenceDuration(style).toString(),
        "max_len" to SUPERTONIC_CHUNK_CHAR_LIMIT.toString()
    )
''')
replace_required(src,
'''        val canonical = Normalizer.normalize(text, Normalizer.Form.NFC)
''',
'''        val canonical = Normalizer.normalize(text, Normalizer.Form.NFKD)
''')

# Update Supertonic generation. Keep seed support; pass the real silence duration option.
replace_required(src,
'''        val silenceScale = if (voice == Voice.SUPERTONIC) effectiveSupertonicSilenceScale(style) else effectiveOfflineSilenceScale(style)
''',
'''        // Supertonic ignores GenerationConfig.silenceScale; its real control is extra.silence_duration.
        val silenceScale = if (voice == Voice.SUPERTONIC) 0.2f else effectiveOfflineSilenceScale(style)
''')
regex_required(src,
    r'(?m)^        val audio = generateRaw\(tts, preparedText, speed, silenceScale, voice, speakerId, onStage, seed\)$',
    '        val audio = generateRaw(tts, preparedText, speed, silenceScale, voice, speakerId, onStage, seed, style)')
replace_required(src,
'''    private fun generateRaw(tts: OfflineTts, text: String, speed: Float, silenceScale: Float, voice: Voice, speakerId: Int, onStage: (String) -> Unit, seed: Int?): GeneratedAudio {
''',
'''    private fun generateRaw(tts: OfflineTts, text: String, speed: Float, silenceScale: Float, voice: Voice, speakerId: Int, onStage: (String) -> Unit, seed: Int?, style: Style): GeneratedAudio {
''')
replace_required(src,
'''                speed = speed, sid = speakerId.coerceIn(0, 9), silenceScale = silenceScale,
                numSteps = SUPERTONIC_HIGH_QUALITY_STEPS,
                extra = mapOf("lang" to "ar", "seed" to (seed ?: 0).toString())
''',
'''                speed = speed, sid = speakerId.coerceIn(0, 9),
                numSteps = SUPERTONIC_HIGH_QUALITY_STEPS,
                extra = supertonicExtraOptions(style, seed ?: 0)
''')

# Remove the optional internal-silence compressor if present in this source variant.
regex_optional(src,
    r'\n    /\*\*\n     \* Supertonic may emit unusually long internal quiet spans\..*?\n    }\n(?=\n    internal fun effectiveOfflineSilenceScale)',
    '\n')
# Remove any call to the optional compressor; keep only boundary trimming.
regex_optional(src,
    r'(?m)^        val prepared = if \(voice == Voice\.SUPERTONIC\) capLongInternalSilence\(trimmed, audio\.sampleRate\) else trimmed\n',
    '')
replace_optional(src,
    'return GeneratedAudio(localAudioWithoutPitchShift(prepared), audio.sampleRate)',
    '// Keep all internal pauses; trim only boundary silence.\n        return GeneratedAudio(localAudioWithoutPitchShift(trimmed), audio.sampleRate)')

# Tests: pause values, Unicode normalization, actual native options and internal-pause preservation.
test = "app/src/test/java/com/sawtiyat/app/audio/ReaderFeatureTest.kt"
replace_optional(test,
'''        assertEquals(260L, OfflineArabicSpeech.SpeechSegment("سؤال؟", 1f).supertonicPauseMs(style))
        assertEquals(180L, OfflineArabicSpeech.SpeechSegment("فكرة؛", 1f).supertonicPauseMs(style))
        assertEquals(120L, OfflineArabicSpeech.SpeechSegment("فكرة،", 1f).supertonicPauseMs(style))
        assertEquals(0L, OfflineArabicSpeech.SpeechSegment("تكملة", 1f).supertonicPauseMs(style))
        assertEquals(266L, OfflineArabicSpeech.SpeechSegment("فقرة.", 1f, paragraphEnd = true).supertonicPauseMs(style))
''',
'''        assertEquals(220L, OfflineArabicSpeech.SpeechSegment("سؤال؟", 1f).supertonicPauseMs(style))
        assertEquals(150L, OfflineArabicSpeech.SpeechSegment("فكرة؛", 1f).supertonicPauseMs(style))
        assertEquals(90L, OfflineArabicSpeech.SpeechSegment("فكرة،", 1f).supertonicPauseMs(style))
        assertEquals(0L, OfflineArabicSpeech.SpeechSegment("تكملة", 1f).supertonicPauseMs(style))
        assertEquals(171L, OfflineArabicSpeech.SpeechSegment("فقرة.", 1f, paragraphEnd = true).supertonicPauseMs(style))
''')
replace_optional(test,
'''        assertEquals(java.text.Normalizer.normalize(source, java.text.Normalizer.Form.NFC), normalized)
''',
'''        assertEquals(java.text.Normalizer.normalize(source, java.text.Normalizer.Form.NFKD), normalized)
''')
replace_optional(test,
'''        assertEquals(style.silenceScale, OfflineArabicSpeech.effectiveSupertonicSilenceScale(style), 0.0001f)
''',
'''        assertEquals(0.22f, OfflineArabicSpeech.effectiveSupertonicSilenceDuration(style), 0.0001f)
        assertEquals(0.12f, OfflineArabicSpeech.effectiveSupertonicSilenceDuration(OfflineArabicSpeech.Style.NEWS), 0.0001f)
        assertTrue(OfflineArabicSpeech.effectiveSupertonicSilenceDuration(style) < 0.3f)
''')
replace_optional(test,
'''    @Test fun supertonicNormalizationRemovesOnlyTatweelAndUnindexedQuranicAnnotation() {
''',
'''    @Test fun supertonicNfkdDecomposesArabicHamzaAndMaddaIntoIndexedMarks() {
        val normalized = OfflineArabicSpeech.normalizeSupertonicText("أَإِآؤئ")
        assertTrue(normalized.contains("ا\\u064E\\u0654"))
        assertTrue(normalized.contains("ا\\u0650\\u0655"))
        assertTrue(normalized.contains("ا\\u0653"))
        assertTrue(normalized.contains("و\\u0654"))
        assertTrue(normalized.contains("ي\\u0654"))
        assertTrue(normalized.any { it.code == 0x064E || it.code == 0x0650 })
    }

    @Test fun supertonicNormalizationRemovesOnlyTatweelAndUnindexedQuranicAnnotation() {
''')
replace_optional(test,
'''    @Test fun supertonicUsesCurrentStyleSpeedAndSilenceSettings() {
''',
'''    @Test fun supertonicPassesSupportedNativeSilenceAndSeedOptions() {
        val options = OfflineArabicSpeech.supertonicExtraOptions(OfflineArabicSpeech.Style.NEWS, 42)
        assertEquals("ar", options["lang"])
        assertEquals("42", options["seed"])
        assertEquals("0.12", options["silence_duration"])
        assertEquals("300", options["max_len"])
    }

    @Test fun supertonicUsesCurrentStyleSpeedAndSilenceSettings() {
''')

# Replace the legacy compressor test only if it exists in this source variant.
p, s = read(test)
pattern = re.compile(r'    @Test fun supertonicCapsOnlyLongInternalSilenceAndPreservesShortPauses\(\) \{.*?\n    }\n', re.S)
replacement = '''    @Test fun supertonicBoundaryTrimRemovesLowLevelPreRollAndPreservesInternalPause() {
        val rate = 1_000
        val leading = FloatArray(2_500) { 0.001f }
        val firstSpeech = FloatArray(500) { 0.2f }
        val internalPause = FloatArray(1_000)
        val secondSpeech = FloatArray(500) { -0.2f }
        val trailing = FloatArray(2_500) { 0.001f }
        val input = leading + firstSpeech + internalPause + secondSpeech + trailing
        val trimmed = OfflineArabicSpeech.trimBoundarySilence(input, rate)
        assertTrue("boundary pre-roll was retained", trimmed.size < input.size - 4_000)
        var longestQuietRun = 0
        var currentQuietRun = 0
        for (sample in trimmed) {
            if (kotlin.math.abs(sample) < 0.0001f) {
                currentQuietRun++
                longestQuietRun = maxOf(longestQuietRun, currentQuietRun)
            } else currentQuietRun = 0
        }
        assertTrue("internal pause was shortened: $longestQuietRun", longestQuietRun >= 900)
    }
'''
s, n = pattern.subn(replacement, s, count=1)
if n:
    write(p, s)

print("Applied Sawtiyat 0.7.22 Supertonic fixes")
