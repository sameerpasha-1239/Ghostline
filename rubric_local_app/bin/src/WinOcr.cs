using System;
using System.IO;
using System.Threading.Tasks;
using Windows.Media.Ocr;
using Windows.Graphics.Imaging;
using Windows.Storage;

namespace RubricOcr {
    class Program {
        static void Main(string[] args) {
            try {
                int code = RunAsync(args).GetAwaiter().GetResult();
                Environment.Exit(code);
            } catch (Exception ex) {
                Console.Error.WriteLine("Fatal Error: " + ex.ToString());
                Environment.Exit(5);
            }
        }

        static async Task<int> RunAsync(string[] args) {
            if (args.Length == 0) {
                Console.Error.WriteLine("Usage: win_ocr.exe <image_path>");
                return 1;
            }
            string path = Path.GetFullPath(args[0]);
            if (!File.Exists(path)) {
                Console.Error.WriteLine("Error: File not found: " + path);
                return 2;
            }

            var fileOp = StorageFile.GetFileFromPathAsync(path);
            var file = await WindowsRuntimeSystemExtensions.AsTask(fileOp);

            var streamOp = file.OpenAsync(FileAccessMode.Read);
            using (var stream = await WindowsRuntimeSystemExtensions.AsTask(streamOp)) {
                var decoderOp = BitmapDecoder.CreateAsync(stream);
                var decoder = await WindowsRuntimeSystemExtensions.AsTask(decoderOp);

                var bitmapOp = decoder.GetSoftwareBitmapAsync();
                var bitmap = await WindowsRuntimeSystemExtensions.AsTask(bitmapOp);
                
                var engine = OcrEngine.TryCreateFromUserProfileLanguages();
                if (engine == null) {
                    engine = OcrEngine.TryCreateFromLanguage(new Windows.Globalization.Language("en-US"));
                }
                if (engine == null) {
                    Console.Error.WriteLine("Error: Could not initialize Windows OCR engine.");
                    return 3;
                }

                var ocrOp = engine.RecognizeAsync(bitmap);
                var result = await WindowsRuntimeSystemExtensions.AsTask(ocrOp);
                
                Console.WriteLine("{");
                Console.WriteLine("  \"text\": " + EscapeJson(result.Text) + ",");
                Console.WriteLine("  \"lines\": [");
                for (int i = 0; i < result.Lines.Count; i++) {
                    string line = result.Lines[i].Text;
                    string comma = (i < result.Lines.Count - 1) ? "," : "";
                    Console.WriteLine("    " + EscapeJson(line) + comma);
                }
                Console.WriteLine("  ]");
                Console.WriteLine("}");
                return 0;
            }
        }

        static string EscapeJson(string s) {
            if (s == null) return "null";
            return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "").Replace("\n", "\\n").Replace("\t", "\\t") + "\"";
        }
    }
}
