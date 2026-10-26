"""Pruebas del clasificador y la geolocalización. Correr con:  python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))

from classify import classify, find_companies, find_parties  # noqa: E402
from proyectos import find_project  # noqa: E402
from collect import process, strip_source_suffix  # noqa: E402
from gazetteer import resolve_location  # noqa: E402


def loc(title, country="AR"):
    return resolve_location(title, len(title), country)


class TestRelevancia(unittest.TestCase):
    POSITIVAS = [
        "YPF construirá una nueva planta de tratamiento de crudo en Añelo",
        "El Gobierno aprobó el RIGI para el proyecto de cobre Los Azules en San Juan",
        "Rio Tinto ampliará su planta de carbonato de litio en Catamarca",
        "Genneia inauguró un nuevo parque solar en Mendoza",
        "Comenzaron las obras del oleoducto Vaca Muerta Oil Sur hacia Punta Colorada",
        "Codelco invertirá US$ 1.500 millones en la expansión de su fundición en Calama",
        "Petrobras anuncia construção de nova unidade de refino em Itaboraí",
        "UTE adjudicó la construcción de una nueva línea de alta tensión en Tacuarembó",
        "Bolivia: YPFB inicia la construcción de una planta de biodiésel en Santa Cruz",
        "Nova usina solar no Pará terá investimento de R$ 2 bilhões",
    ]
    NEGATIVAS = [
        "El precio del petróleo cae por temor a una recesión global",
        "Récord de producción de petróleo en Vaca Muerta en septiembre",
        "Las acciones de YPF suben en Wall Street",
        "Aumentan las tarifas de gas en Buenos Aires desde noviembre",
        "Boca ganó el clásico y amplía su ventaja en el torneo",
        "La inflación de septiembre fue de 2,1%",
    ]

    def test_positivas(self):
        for t in self.POSITIVAS:
            with self.subTest(t=t):
                self.assertIsNotNone(classify(t), t)

    def test_negativas(self):
        for t in self.NEGATIVAS:
            with self.subTest(t=t):
                self.assertIsNone(classify(t), t)

    def test_sectores(self):
        self.assertEqual(classify("Genneia inauguró un nuevo parque solar en Mendoza")["sectors"][0], "energia")
        self.assertEqual(classify("Rio Tinto ampliará su planta de carbonato de litio en Catamarca")["sectors"][0], "mineria")
        self.assertEqual(classify("Comenzaron las obras del oleoducto Vaca Muerta Oil Sur")["sectors"][0], "oilgas")

    def test_senal_rigi(self):
        self.assertIn("rigi", classify("El Gobierno aprobó el RIGI para el proyecto de cobre Los Azules")["signals"])


class TestUbicacion(unittest.TestCase):
    def test_ciudad_gana_a_provincia(self):
        r = loc("Nueva planta en Añelo, Neuquén")
        self.assertEqual((r["city"], r["admin1"]), ("Añelo", "Neuquén"))

    def test_ambiguo_por_pais_de_la_fuente(self):
        self.assertEqual(loc("Nueva planta en Santa Cruz", "AR")["country"], "AR")
        self.assertEqual(loc("Nueva planta en Santa Cruz", "BO")["country"], "BO")

    def test_pais_mencionado(self):
        self.assertEqual(loc("Chile: SQM ampliará su planta en el Salar de Atacama")["country"], "CL")

    def test_apellido_no_es_lugar(self):
        self.assertIsNone(loc("Juan Rivera anunció una nueva planta"))

    def test_para_no_es_pará(self):
        self.assertIsNone(loc("Nova planta para a região", "BR"))
        self.assertEqual(loc("Nova planta no Pará", "BR")["admin1"], "Pará")

    def test_sin_lugar(self):
        self.assertIsNone(loc("Nueva planta de litio anunciada"))


class TestEmpresas(unittest.TestCase):
    def test_diccionario(self):
        self.assertEqual(find_companies("YPF y Pan American Energy ampliarán el oleoducto"), ["YPF", "Pan American Energy"])

    def test_heuristica(self):
        self.assertEqual(find_companies("La empresa Andes Power construirá un parque solar"), ["Andes Power"])


class TestSegundoAnillo(unittest.TestCase):
    def test_contratista_conocido(self):
        self.assertEqual(find_parties("YPF adjudicó a SACDE la construcción de la planta en Añelo"), (["YPF"], ["SACDE"]))

    def test_contratista_por_frase(self):
        self.assertEqual(find_parties("La obra será ejecutada por la empresa Petrotec del Sur")[1], ["Petrotec del Sur"])

    def test_ute_no_es_la_electrica_uruguaya(self):
        owners, contractors = find_parties("TGS licitó el gasoducto; la UTE Techint-SACDE ejecutará la obra")
        self.assertNotIn("UTE", owners)
        self.assertIn("SACDE", contractors)


class TestProyectos(unittest.TestCase):
    def test_nombre(self):
        self.assertEqual(find_project("Avanza el oleoducto Vaca Muerta Oil Sur hacia Punta Colorada"), "VMOS (Vaca Muerta Oil Sur)")

    def test_ciudad_no_es_proyecto(self):
        self.assertIsNone(find_project("Nueva planta en Perito Moreno, Santa Cruz"))


class TestProceso(unittest.TestCase):
    def test_sufijo_google(self):
        self.assertEqual(strip_source_suffix("Nueva planta en Salta - Diario X", "Diario X"), "Nueva planta en Salta")

    def test_item_completo(self):
        item = process({"title": "Tecpetrol construirá una nueva planta de gas en Neuquén - Río Negro", "source": "Río Negro", "url": "https://x", "summary": "", "date": None}, "AR", "test")
        self.assertEqual(item["admin1"], "Neuquén")
        self.assertIn("Tecpetrol", item["companies"])
        self.assertIn("oilgas", item["sectors"])


if __name__ == "__main__":
    unittest.main()
