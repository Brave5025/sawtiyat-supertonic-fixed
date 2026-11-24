from pathlib import Path
import re

ROOT = Path("source/Sawtiyat-0.7.14-source")

def replace_once(path, old, new):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path}, found {count}: {old[:100]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

# Version identity for the clean-install 0.7.21 build.
p = ROOT / "app/build.gradle.kts"
s = p.read_text(encoding="utf-8")
s, n1 = re.subn(r'versionCode\s*=\s*\d+', 'versionCode = 37', s, count=1)
s, n2 = re.subn(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.7.21"', s, count=1)
if n1 != 1 or n2 != 1:
    raise SystemExit("Could not update Android versionCode/versionName")
p.write_text(s, encoding="utf-8")

src = "app/src/main/java/com/sawtiyat/app/audio/OfflineArabicSpeech.kt"
replace_once(src, "import java.io.File\n", "import java.io.File\nimport java.security.MessageDigest\n")
replace_once(src,
'''    /** إعداد Supertonic من إصدار 0.7.9: سرعة المستخدم مع معامل نمط القراءة. */
    internal fun effectiveSupertonicSpeed(rate: Float, style: Style): Float =
        (rate * style.speedFactor).coerceIn(0.7f, 2f)
''',
'''    /** حد أدنى محافظ لـSupertonic لتقليل تكرار المقاطع المرصود عند السرعات المنخفضة. */
    internal fun effectiveSupertonicSpeed(rate: Float, style: Style): Float =
        (rate * style.speedFactor.coerceAtLeast(0.9f)).coerceIn(0.9f, 2f)

    /** بذرة ثابتة لكل مقطع، مرتبطة بالنص الكامل ورقم المقطع ومحتواه. */
    internal fun deterministicSupertonicSeed(documentText: String, segmentIndex: Int, segmentText: String): Int {
        val digest = MessageDigest.getInstance("SHA-256").digest(
            (normalizeSupertonicText(documentText) + "\\u0000" + segmentIndex + "\\u0000" + normalizeSupertonicText(segmentText))
                .toByteArray(Charsets.UTF_8)
        )
        val value = ((digest[0].toLong() and 0xff) shl 24) or
            ((digest[1].toLong() and 0xff) shl 16) or
            ((digest[2].toLong() and 0xff) shl 8) or (digest[3].toLong() and 0xff)
        return (value and 0x7fffffffL).toInt()
    }
''')
replace_once(src,
'''            writeWav(tts, chunks, staged, rate, style, voice, speakerId)
''',
'''            writeWav(tts, chunks, staged, rate, style, voice, speakerId, text)
''')
replace_once(src,
'''    internal fun generateChunk(tts: OfflineTts, text: String, rate: Float, style: Style, voice: Voice = Voice.NABRA, speakerId: Int = 0, onStage: (String) -> Unit = {}): GeneratedAudio {
        val speed = if (voice == Voice.SUPERTONIC) effectiveSupertonicSpeed(rate, style) else effectiveOfflineSpeed(rate, style)
        val silenceScale = if (voice == Voice.SUPERTONIC) effectiveSupertonicSilenceScale(style) else effectiveOfflineSilenceScale(style)
        val preparedText = if (voice == Voice.SUPERTONIC) normalizeSupertonicText(text) else text
        check(preparedText.isNotBlank()) { "لا يوجد نص قابل للنطق بعد تطبيع التشكيل" }
        val audio = generateRaw(tts, preparedText, speed, silenceScale, voice, speakerId, onStage)
        val prepared = prepareGeneratedSamples(audio.samples, audio.sampleRate, style, voice)
        return GeneratedAudio(prepared, audio.sampleRate)
    }
''',
'''    internal fun generateChunk(tts: OfflineTts, text: String, rate: Float, style: Style, voice: Voice = Voice.NABRA, speakerId: Int = 0, onStage: (String) -> Unit = {}, seedDocument: String = text, segmentIndex: Int = 0): GeneratedAudio {
        val speed = if (voice == Voice.SUPERTONIC) effectiveSupertonicSpeed(rate, style) else effectiveOfflineSpeed(rate, style)
        val silenceScale = if (voice == Voice.SUPERTONIC) effectiveSupertonicSilenceScale(style) else effectiveOfflineSilenceScale(style)
        val preparedText = if (voice == Voice.SUPERTONIC) normalizeSupertonicText(text) else text
        check(preparedText.isNotBlank()) { "لا يوجد نص قابل للنطق بعد تطبيع التشكيل" }
        val seed = if (voice == Voice.SUPERTONIC) deterministicSupertonicSeed(seedDocument, segmentIndex, preparedText) else null
        val audio = generateRaw(tts, preparedText, speed, silenceScale, voice, speakerId, onStage, seed)
        val prepared = prepareGeneratedSamples(audio.samples, audio.sampleRate, style, voice)
        return GeneratedAudio(prepared, audio.sampleRate)
    }
''')
replace_once(src,
'''    private fun generateRaw(tts: OfflineTts, text: String, speed: Float, silenceScale: Float, voice: Voice, speakerId: Int, onStage: (String) -> Unit): GeneratedAudio {
''',
'''    private fun generateRaw(tts: OfflineTts, text: String, speed: Float, silenceScale: Float, voice: Voice, speakerId: Int, onStage: (String) -> Unit, seed: Int?): GeneratedAudio {
''')
replace_once(src,
'''                numSteps = SUPERTONIC_HIGH_QUALITY_STEPS, extra = mapOf("lang" to "ar")
''',
'''                numSteps = SUPERTONIC_HIGH_QUALITY_STEPS,
                extra = mapOf("lang" to "ar", "seed" to (seed ?: 0).toString())
''')
replace_once(src,
'''    private fun writeWav(tts: OfflineTts, chunks: List<SpeechSegment>, output: File, rate: Float, style: Style, voice: Voice, speakerId: Int) {
''',
'''    private fun writeWav(tts: OfflineTts, chunks: List<SpeechSegment>, output: File, rate: Float, style: Style, voice: Voice, speakerId: Int, seedDocument: String) {
''')
replace_once(src,
'''                val audio = generateChunk(tts, chunk.text, rate, style, voice, speakerId)
''',
'''                val audio = generateChunk(tts, chunk.text, rate, style, voice, speakerId, seedDocument = seedDocument, segmentIndex = index)
''')
# Keep only boundary trimming: do not shorten internal pauses or alter local voice pitch.
replace_once(src,
'''        return if (voice == Voice.SUPERTONIC) trimmed else applyPerformancePitch(trimmed, style)
''',
'''        return trimmed
''')

service = "app/src/main/java/com/sawtiyat/app/audio/OfflineSpeechService.kt"
replace_once(service,
'''                                            liveRate, liveStyle, liveVoice, liveSpeakerId
                                        ) { s -> stage = s }
''',
'''                                            liveRate, liveStyle, liveVoice, liveSpeakerId,
                                            onStage = { s -> stage = s },
                                            seedDocument = voicedBody, segmentIndex = index
                                        )
''')

test = "app/src/test/java/com/sawtiyat/app/audio/ReaderFeatureTest.kt"
replace_once(test, "assertEquals(0.72f, OfflineArabicSpeech.effectiveSupertonicSpeed(1f, style), 0.0001f)", "assertEquals(0.9f, OfflineArabicSpeech.effectiveSupertonicSpeed(1f, style), 0.0001f)")
replace_once(test, "assertEquals(0.7f, OfflineArabicSpeech.effectiveSupertonicSpeed(0.5f, OfflineArabicSpeech.Style.DOCUMENTARY), 0.0001f)", "assertEquals(0.9f, OfflineArabicSpeech.effectiveSupertonicSpeed(0.5f, OfflineArabicSpeech.Style.DOCUMENTARY), 0.0001f)")
# Replace obsolete cap-compression test with a preservation test based on boundary-only trimming.
p = ROOT / test
s = p.read_text(encoding="utf-8")
pattern = re.compile(r'    @Test fun supertonicCapsOnlyLongInternalSilenceAndPreservesShortPauses\(\) \{.*?\n    \}\n', re.S)
replacement = '''    @Test fun boundaryTrimmingPreservesLongInternalPause() {
        val rate = 1_000
        val voiced = FloatArray(rate / 2) { 0.2f }
        val longGap = FloatArray(rate) { 0f }
        val input = voiced + longGap + voiced
        val trimmed = OfflineArabicSpeech.trimBoundarySilence(input, rate)
        assertEquals(input.size, trimmed.size)
        assertEquals(rate, trimmed.slice(rate / 2 until rate / 2 + rate).count { it == 0f })
    }
'''
s, n = pattern.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit("Could not replace obsolete internal-silence compression test")
p.write_text(s, encoding="utf-8")

# Deterministic seed regression coverage.
p = ROOT / test
s = p.read_text(encoding="utf-8")
marker = '''    @Test fun localTtsTrimsOnlyBoundarySilenceAndRetainsSpeechWithMargin() {
'''
addition = '''    @Test fun supertonicSeedIsStableAndChangesWithDocumentOrSegment() {
        val document = "هذا نص عربي للاختبار"
        val segment = "هذا نص"
        val seed = OfflineArabicSpeech.deterministicSupertonicSeed(document, 0, segment)
        assertEquals(seed, OfflineArabicSpeech.deterministicSupertonicSeed(document, 0, segment))
        assertTrue(seed != OfflineArabicSpeech.deterministicSupertonicSeed(document, 1, segment))
        assertTrue(seed != OfflineArabicSpeech.deterministicSupertonicSeed(document + " ", 0, segment))
    }

'''
if marker not in s:
    raise SystemExit("Could not find test insertion marker")
p.write_text(s.replace(marker, addition + marker, 1), encoding="utf-8")

print("Applied Sawtiyat 0.7.21 audio/version patch")
