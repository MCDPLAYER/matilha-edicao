"""Testes rápidos, sem mídia e sem ffmpeg:  python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edicao import ajustes, audio, vaos, zoom          # noqa: E402
from edicao.config import FPS, SPF, SR                 # noqa: E402
from edicao.mapa import Mapa                           # noqa: E402


class TestMapa(unittest.TestCase):
    def test_corte_e_insercao(self):
        # bruto de 1000 quadros; tira [100,200); abre 50 quadros no quadro 500
        m = Mapa(1000, [(100, 200)], [dict(fc=500, n=50, slot="CAP")])
        self.assertEqual(m.saida(50), 50)
        self.assertEqual(m.saida(300), 200)            # depois do corte: -100
        self.assertEqual(m.saida(500, "ini"), 450)     # a inserção em 500 vem ANTES do quadro 500
        self.assertEqual(m.saida(500, "fim"), 400)     # um intervalo que termina em 500 termina antes dela
        self.assertEqual(m.n_saida, 1000 - 100 + 50)

    def test_cortes_que_se_tocam_sao_fundidos(self):
        m = Mapa(1000, [(100, 200), (150, 250), (250, 300)], [])
        self.assertEqual(m.cortes, [(100, 300)])

    def test_segmentos_cobrem_a_saida_sem_buraco(self):
        m = Mapa(1000, [(100, 200)], [dict(fc=500, n=50, slot="CAP"), dict(fc=0, n=10, slot="ABERTURA")])
        segs = m.segmentos()
        self.assertEqual(segs[0]["a"], 0)
        for s0, s1 in zip(segs, segs[1:]):
            self.assertEqual(s0["b"], s1["a"])
        self.assertEqual(segs[-1]["b"], m.n_saida)
        self.assertEqual(sum(1 for s in segs if s["tipo"] == "ins"), 2)


class TestVaos(unittest.TestCase):
    def test_fecha_vao_curto_estendendo_a_midia(self):
        cam = [dict(camada="midia", slot="M1", a=0, b=100), dict(camada="card", slot="C1", a=130, b=200)]
        av: list = []
        ok, resto = vaos.fechar_gui_solto(cam, av)
        self.assertEqual((ok, resto), (1, 0))
        self.assertEqual(cam[0]["b"], 130)

    def test_vao_longo_fica(self):
        cam = [dict(camada="midia", slot="M1", a=0, b=100), dict(camada="card", slot="C1", a=100 + 2 * FPS, b=400)]
        ok, resto = vaos.fechar_gui_solto(cam, [])
        self.assertEqual((ok, resto), (0, 0))

    def test_puxar_volta_na_fonte(self):
        c = dict(a=100, b=200, partes=[dict(ss=2.0, disp=3.0)])
        vaos.puxar(c, FPS // 2)
        self.assertEqual(c["a"], 100 - FPS // 2)
        self.assertAlmostEqual(c["partes"][0]["ss"], 1.5)
        self.assertAlmostEqual(c["partes"][0]["disp"], 3.5)


class TestZoom(unittest.TestCase):
    Z = dict(foco=[0.5, 0.3], chaves=[dict(t0=1.0, t1=2.0, s0=1.0, s1=1.2, bezier=[0.4, 0.0, 0.2, 1.0])])

    def test_escala_antes_durante_depois(self):
        self.assertEqual(zoom.escala_zoom(self.Z, 0.0), 1.0)
        self.assertAlmostEqual(zoom.escala_zoom(self.Z, 5.0), 1.2)
        meio = zoom.escala_zoom(self.Z, 1.5)
        self.assertTrue(1.0 < meio < 1.2)

    def test_curva_nao_e_linear(self):
        # com ease-in-out forte, 25% do tempo NÃO é 25% do caminho
        self.assertNotAlmostEqual(zoom.bezier(0.25, 0.65, 0.0, 0.35, 1.0), 0.25, places=2)

    def test_estica_ou_vaivem(self):
        fator, vai = zoom.plano_estica(3.0, 2.5)
        self.assertFalse(vai)
        self.assertGreaterEqual(fator, 1.0)
        self.assertEqual(zoom.plano_estica(10.0, 2.0), (zoom.LENTO_VAIVEM, True))

    def test_filtro_agrupa_termos(self):
        f = zoom.zoompan_filtro(self.Z, 0, 200, 1280, 720)
        self.assertIn("zoompan=", f)
        self.assertGreaterEqual(f.count("(("), 0)


class TestAudio(unittest.TestCase):
    def test_vo_enxuto_encolhe_pausas(self):
        t = np.arange(SR) / SR
        tom = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        sil = np.zeros(SR, np.float32)     # 1 s de silêncio
        mono = np.concatenate([sil, tom, sil, tom, sil])
        d = np.stack([mono, mono], axis=1)
        e = audio.vo_enxuto(d)
        # 2 s de fala + pausa interna encolhida + bordas curtas: bem menor que os 5 s originais
        self.assertLess(len(e) / SR, 2.6)
        self.assertGreater(len(e) / SR, 2.0)

    def test_envelope_so_onde_tem_ajuste(self):
        aj = dict(audio=[dict(id="A", a=10, b=20, voz=0, trilha=-6, sfx=0)])
        self.assertIsNone(ajustes.envelope(aj, "voz", 0, 100 * SPF, SR, SPF))
        env = ajustes.envelope(aj, "trilha", 0, 100 * SPF, SR, SPF)
        self.assertAlmostEqual(float(env[15 * SPF]), 10 ** (-6 / 20), places=3)
        self.assertAlmostEqual(float(env[50 * SPF]), 1.0, places=3)

    def test_filtro_master(self):
        f = audio.filtro_master(-1.7)
        self.assertIn("volume=-1.70dB", f)
        self.assertIn("alimiter", f)

    def test_db_lin(self):
        self.assertAlmostEqual(float(audio.db_lin(-6.0206)), 0.5, places=3)


if __name__ == "__main__":
    unittest.main()
