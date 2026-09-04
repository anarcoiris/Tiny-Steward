"""Smoke tests for all scripts in skills/file_utilities/."""

import sys
import tempfile
import unittest
from pathlib import Path

# Add skill scripts to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "checksums-verifier" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "diff-visualizer" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "git-patch-manager" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "directory-tree-generator" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "config-loader" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "file-operations" / "scripts"))
sys.path.insert(0, str(BASE_DIR / "skills" / "file_utilities" / "encoding-detector" / "scripts"))


class TestSkillsFileUtilities(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.file_a = self.temp / "sample_a.txt"
        self.file_b = self.temp / "sample_b.txt"

        self.file_a.write_text("line 1\nline 2\nline 3\ncommon\n", encoding="utf-8")
        self.file_b.write_text("line 1\nline 2 modified\nline 3\ncommon\nnew line\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_checksums_verifier(self):
        from checksums import calcular_checksum, verificar_checksum, generar_manifest

        sha = calcular_checksum(str(self.file_a), algoritmo="sha256")
        self.assertEqual(len(sha), 64)
        self.assertTrue(verificar_checksum(str(self.file_a), sha, algoritmo="sha256"))

        manifest = generar_manifest(str(self.temp), algoritmo="sha256")
        self.assertIn("sample_a.txt", manifest)
        self.assertIn("sample_b.txt", manifest)

    def test_diff_visualizer(self):
        from diff_visualizer import dif_unificado, resumen_dif, dif_lado_al_lado, comparar_directorios

        # Test unified diff
        diff = dif_unificado(str(self.file_a), str(self.file_b), contexto=2)
        self.assertTrue(len(diff) > 0)
        self.assertTrue(any("---" in l or "+++" in l for l in diff))

        # Test summary
        resumen = resumen_dif(str(self.file_a), str(self.file_b))
        self.assertNotIn("error", resumen)
        self.assertEqual(resumen["lineas_archivo_a"], 4)
        self.assertEqual(resumen["lineas_archivo_b"], 5)
        self.assertTrue(resumen["lineas_agregadas"] >= 1)

        # Test side by side
        side = dif_lado_al_lado(str(self.file_a), str(self.file_b))
        self.assertTrue(len(side) > 2)

        # Test compare dirs
        sub_a = self.temp / "dir_a"
        sub_b = self.temp / "dir_b"
        sub_a.mkdir()
        sub_b.mkdir()
        (sub_a / "f1.txt").write_text("a", encoding="utf-8")
        (sub_b / "f1.txt").write_text("b", encoding="utf-8")
        (sub_b / "f2.txt").write_text("new", encoding="utf-8")

        comp = comparar_directorios(str(sub_a), str(sub_b))
        self.assertIn("f2.txt", comp["nuevos"])
        self.assertEqual(len(comp["modificados"]), 1)

    def test_git_patch_generator(self):
        from git_patch_generator import (
            generar_diff_unificado,
            generar_patch,
            aplicar_patch,
            resumen_cambios,
            diff_lado_al_lado,
        )

        diff = generar_diff_unificado(str(self.file_a), str(self.file_b), contexto=2)
        self.assertTrue(len(diff) > 0)

        # Test patch generation
        patch_text = generar_patch(str(self.file_a), str(self.file_b), contexto=2)
        self.assertIn("---", patch_text)
        self.assertIn("+++", patch_text)

        # Test applying patch to a copy of file_a
        target_copy = self.temp / "target_copy.txt"
        target_copy.write_text(self.file_a.read_text(encoding="utf-8"), encoding="utf-8")
        result = aplicar_patch(str(target_copy), patch_text)
        self.assertNotIn("error", result)
        self.assertEqual(target_copy.read_text(encoding="utf-8"), self.file_b.read_text(encoding="utf-8"))

        # Test resumen_cambios and side by side
        resumen = resumen_cambios(str(self.file_a), str(self.file_b))
        self.assertEqual(resumen["lineas_totales_original"], 4)
        self.assertEqual(resumen["lineas_totales_modificadas"], 5)

        side = diff_lado_al_lado(str(self.file_a), str(self.file_b))
        self.assertTrue(len(side) >= 3)

        # Test patch on new file
        new_target = self.temp / "brand_new.txt"
        patch_new = generar_patch(str(self.file_a), str(self.file_b))
        res_new = aplicar_patch(str(new_target), patch_new, crear_archivo=True)
        self.assertNotIn("error", res_new)
        self.assertTrue(new_target.exists())

    def test_file_operations(self):
        from file_operations import (
            copiar_archivo,
            mover_archivo,
            renombrar_archivo,
            truncar_archivo,
            anteponer_lineas,
            anexar_lineas,
            eliminar_archivo_seguro,
            restaurar_backup,
        )

        # 1. Copiar
        copia = self.temp / "copia.txt"
        res_copy = copiar_archivo(str(self.file_a), str(copia))
        self.assertNotIn("error", res_copy)
        self.assertTrue(copia.exists())

        # 2. Renombrar
        res_ren = renombrar_archivo(str(copia), "copia_renombrada.txt")
        self.assertNotIn("error", res_ren)
        renombrado = self.temp / "copia_renombrada.txt"
        self.assertTrue(renombrado.exists())

        # 3. Mover
        sub = self.temp / "subdir"
        res_mov = mover_archivo(str(renombrado), str(sub / "movido.txt"))
        self.assertNotIn("error", res_mov)
        movido = sub / "movido.txt"
        self.assertTrue(movido.exists())

        # 4. Prepend & Append
        anteponer_lineas(str(movido), ["# Linea 0\n"])
        anexar_lineas(str(movido), ["# Linea Final\n"])
        lineas = movido.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lineas[0], "# Linea 0")
        self.assertEqual(lineas[-1], "# Linea Final")

        # 5. Truncar
        truncar_archivo(str(movido), tamanio_bytes=0)
        self.assertEqual(movido.stat().st_size, 0)

        # 6. Eliminar con backup & restaurar
        res_del = eliminar_archivo_seguro(str(movido), con_backup=True)
        self.assertFalse(movido.exists())
        self.assertIsNotNone(res_del.get("backup_disponible"))
        bak_path = res_del["backup_disponible"]
        self.assertTrue(Path(bak_path).exists())

        res_rest = restaurar_backup(bak_path, str(movido))
        self.assertNotIn("error", res_rest)
        self.assertTrue(movido.exists())

    def test_encoding_detector(self):
        from encoding_detector import (
            detectar_codificacion,
            convertir_codificacion,
            es_archivo_binario,
        )

        # 1. Test ASCII
        ascii_file = self.temp / "ascii.txt"
        ascii_file.write_bytes(b"Simple plain ASCII text without accents\n")
        det_ascii = detectar_codificacion(str(ascii_file))
        self.assertEqual(det_ascii["encoding"], "ascii")
        self.assertTrue(det_ascii["is_ascii"])

        # 2. Test UTF-8 con acentos
        utf8_file = self.temp / "utf8.txt"
        utf8_file.write_text("Texto con acentos: áéíóú, ñ, ¿qué tal?", encoding="utf-8")
        det_utf8 = detectar_codificacion(str(utf8_file))
        self.assertEqual(det_utf8["encoding"], "utf-8")
        self.assertFalse(det_utf8["is_ascii"])

        # 3. Test UTF-8 with BOM
        bom_file = self.temp / "utf8_bom.txt"
        bom_file.write_bytes(b"\xef\xbb\xbf" + "Contenido con BOM UTF-8".encode("utf-8"))
        det_bom = detectar_codificacion(str(bom_file))
        self.assertEqual(det_bom["encoding"], "utf-8-sig")
        self.assertTrue(det_bom["has_bom"])

        # 4. Test Conversión a UTF-16 y detección
        utf16_file = self.temp / "converted_utf16.txt"
        res_conv = convertir_codificacion(
            str(utf8_file),
            str(utf16_file),
            codificacion_destino="utf-16-le",
        )
        self.assertNotIn("error", res_conv)
        self.assertTrue(utf16_file.exists())

        det_utf16 = detectar_codificacion(str(utf16_file))
        self.assertIn("utf-16", det_utf16["encoding"])

        # 5. Test Binario vs Texto
        bin_file = self.temp / "sample.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03\x04\xff\xfe\x00\x00\x05")
        self.assertTrue(es_archivo_binario(str(bin_file)))
        self.assertFalse(es_archivo_binario(str(utf8_file)))


if __name__ == "__main__":
    unittest.main()
