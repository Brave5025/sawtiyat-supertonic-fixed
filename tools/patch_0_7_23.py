from pathlib import Path
import re

ROOT = Path("source/Sawtiyat-0.7.14-source")

def edit(path, old, new):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    if s.count(old) != 1:
        raise SystemExit(f"Expected exactly one match in {path}: {old[:80]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")

p = ROOT / "app/build.gradle.kts"
s = p.read_text(encoding="utf-8")
s, a = re.subn(r'versionCode\s*=\s*\d+', "versionCode = 39", s, count=1)
s, b = re.subn(r'versionName\s*=\s*"[^"]+"', 'versionName = "0.7.23"', s, count=1)
if a != 1 or b != 1: raise SystemExit("Could not set version 0.7.23")
p.write_text(s, encoding="utf-8")

path = "app/src/main/java/com/sawtiyat/app/audio/LocalModelStore.kt"
p = ROOT / path
s = p.read_text(encoding="utf-8")
s = s.replace("import kotlinx.coroutines.Dispatchers\n", "import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.delay\nimport kotlinx.coroutines.CancellationException\n", 1)
p.write_text(s, encoding="utf-8")

edit(path,
'    const val ICHKIL_SHA = "9779e1aca89cebc77a9b92037b7d700c422cdf6c3774d4883f4652f641f3f705"\n',
'    const val ICHKIL_SHA = "9779e1aca89cebc77a9b92037b7d700c422cdf6c3774d4883f4652f641f3f705"\n    private const val ICHKIL_MODEL_BYTES = 22_284_311L\n    private const val ICHKIL_CONFIG_BYTES = 3_060L\n')
edit(path,
'''        return File(d, "model.onnx").let { it.isFile && it.length() == 22_284_311L } &&
            File(d, "config.json").let { it.isFile && it.length() == 3_060L }
''',
'''        return verifyArtifact(File(d, "model.onnx"), ICHKIL_SHA, ICHKIL_MODEL_BYTES) &&
            verifyArtifact(File(d, "config.json"), ICHKIL_CONFIG_SHA, ICHKIL_CONFIG_BYTES)
''')
edit(path,
'''        download("model.onnx", "$base/model.onnx", File(dir, "model.onnx"), ICHKIL_SHA, onProgress)
        download("config.json", "$base/config.json", File(dir, "config.json"), ICHKIL_CONFIG_SHA, onProgress)
''',
'''        download("model.onnx", "$base/model.onnx", File(dir, "model.onnx"), ICHKIL_SHA, onProgress, ICHKIL_MODEL_BYTES)
        download("config.json", "$base/config.json", File(dir, "config.json"), ICHKIL_CONFIG_SHA, onProgress, ICHKIL_CONFIG_BYTES)
''')

p = ROOT / path
s = p.read_text(encoding="utf-8")
start = s.index("    private suspend fun download(")
end = s.index("\n    private fun verified(", start)
replacement = r'''
    private suspend fun download(
        name: String,
        url: String,
        dest: File,
        expected: String?,
        onProgress: (Progress) -> Unit,
        expectedBytes: Long? = null
    ) {
        if (dest.isFile && (expected == null || verifyArtifact(dest, expected, expectedBytes))) return
        dest.parentFile?.mkdirs()
        var lastError: Exception? = null
        for (attempt in 1..3) {
            val part = File(dest.parentFile, dest.name + ".part")
            part.delete()
            val suffix = if (attempt == 1) "" else
                (if (url.contains("?")) "&" else "?") + "download=true&sv_retry=$attempt"
            val conn = (URL(url + suffix).openConnection() as HttpURLConnection).apply {
                connectTimeout = 30000
                readTimeout = 120000
                instanceFollowRedirects = true
                useCaches = false
                setRequestProperty("User-Agent", "Sawtiyat-Android/0.7.23")
                setRequestProperty("Accept-Encoding", "identity")
                setRequestProperty("Cache-Control", "no-cache")
                setRequestProperty("Pragma", "no-cache")
            }
            try {
                conn.connect()
                val status = conn.responseCode
                check(status in 200..299) { "HTTP $status أثناء تنزيل $name" }
                val declared = conn.contentLengthLong
                if (expectedBytes != null && declared > 0L) {
                    check(declared == expectedBytes) {
                        "حجم $name المعلن غير صحيح: $declared بايت، المتوقع $expectedBytes"
                    }
                }
                var received = 0L
                conn.inputStream.use { input ->
                    FileOutputStream(part).use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            currentCoroutineContext().ensureActive()
                            val count = input.read(buffer)
                            if (count < 0) break
                            if (count == 0) continue
                            output.write(buffer, 0, count)
                            received += count
                            onProgress(Progress(name, received, expectedBytes ?: declared.coerceAtLeast(0L)))
                        }
                        output.fd.sync()
                    }
                }
                check(received > 0L) { "الخادم أعاد ملفًا فارغًا لـ$name" }
                if (expectedBytes != null) check(received == expectedBytes) {
                    "التنزيل غير مكتمل لـ$name: وصل $received من $expectedBytes بايت"
                }
                if (expected != null) {
                    val actual = sha256(part)
                    check(actual.equals(expected, ignoreCase = true)) {
                        "فشل فحص سلامة $name: الحجم $received بايت، والبصمة المستلمة $actual"
                    }
                }
                if (dest.exists()) check(dest.delete()) { "تعذر استبدال الملف القديم $name" }
                check(part.renameTo(dest)) { "تعذر حفظ $name بعد التحقق" }
                return
            } catch (error: Exception) {
                part.delete()
                if (error is CancellationException) throw error
                lastError = error
                if (attempt < 3) delay(600L * attempt)
            } finally {
                conn.disconnect()
            }
        }
        throw IllegalStateException(
            "تعذر تنزيل $name بعد 3 محاولات. آخر سبب: " + (lastError?.message ?: "خطأ غير معروف"),
            lastError
        )
    }
'''
s = s[:start] + replacement + s[end:]
p.write_text(s, encoding="utf-8")

edit(path,
'''    private fun verified(file: File, hash: String): Boolean = file.isFile && runCatching { sha256(file).equals(hash, true) }.getOrDefault(false)
''',
'''    internal fun verifyArtifact(file: File, hash: String, expectedBytes: Long? = null): Boolean {
        if (!file.isFile) return false
        if (expectedBytes != null && file.length() != expectedBytes) return false
        return runCatching { sha256(file).equals(hash, ignoreCase = true) }.getOrDefault(false)
    }

    private fun verified(file: File, hash: String): Boolean = verifyArtifact(file, hash)
''')

test = ROOT / "app/src/test/java/com/sawtiyat/app/audio/LocalModelStoreDownloadTest.kt"
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text("""package com.sawtiyat.app.audio

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class LocalModelStoreDownloadTest {
    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    @Test fun acceptsOnlyExactLengthAndPinnedSha256() {
        val bytes = "verified model fixture".toByteArray()
        val file = File.createTempFile("sawtiyat-model-", ".bin")
        try {
            file.writeBytes(bytes)
            assertTrue(LocalModelStore.verifyArtifact(file, sha256(bytes), bytes.size.toLong()))
            assertFalse(LocalModelStore.verifyArtifact(file, sha256(bytes), bytes.size.toLong() + 1L))
            assertFalse(LocalModelStore.verifyArtifact(file, "0".repeat(64), bytes.size.toLong()))
        } finally {
            file.delete()
        }
    }
}
""", encoding="utf-8")

print("Applied Sawtiyat 0.7.23 model-download integrity fix")
