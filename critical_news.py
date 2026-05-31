"""
critical_news.py - Materyal ve teknoloji kisitlamasi haberlerini isaretle
InP (Indium Phosphide), GaAs (Gallium Arsenide), SiC, GaN, China export ban vs.
"""
from __future__ import annotations

import re

# Anahtar terimler -> kategori + onem agirligi (1..3)
CRITICAL_TERMS: dict[str, tuple[str, int]] = {
    # Materyaller (yari iletken)
    "indium phosphide": ("Materyal: InP", 3),
    "inp wafer":         ("Materyal: InP wafer", 3),
    "gallium arsenide":  ("Materyal: GaAs", 3),
    "gaas":              ("Materyal: GaAs", 2),
    "silicon carbide":   ("Materyal: SiC", 3),
    "sic substrate":     ("Materyal: SiC wafer", 3),
    "gallium nitride":   ("Materyal: GaN", 3),
    "gan power":         ("Materyal: GaN", 2),
    "rare earth":        ("Nadir Element", 3),
    "gallium ":          ("Materyal: Galyum", 2),
    "germanium":         ("Materyal: Germanyum", 2),
    "neodymium":         ("Nadir Element: Neodimyum", 2),
    "lithium":           ("Lityum", 1),

    # Ihracat/cip kontrolu
    "export control":    ("Ihracat Kisitlamasi", 3),
    "export ban":        ("Ihracat Yasagi", 3),
    "export restriction":("Ihracat Kisitlamasi", 3),
    "sanction":          ("Yaptirim", 3),
    "tariff":            ("Gumruk Tarifesi", 2),
    "chips act":         ("CHIPS Act", 3),
    "entity list":       ("ABD Entity List", 3),
    "ofac":              ("OFAC Yaptirim", 3),
    "huawei ban":        ("Huawei Yasagi", 3),
    "ymtc":              ("YMTC Kisiti", 3),

    # Cin-ABD tekno savasi
    "tech war":          ("Cin-ABD Tekno Savasi", 3),
    "china-us":          ("Cin-ABD Geriilim", 2),
    "us-china":          ("Cin-ABD Geriilim", 2),
    "decoupling":        ("Tekno Decoupling", 3),
    "geopolitical":      ("Jeopolitik", 2),
    "tsmc taiwan":       ("Tayvan Riski", 3),
    "taiwan tension":    ("Tayvan Tansiyonu", 3),
    "made in china":     ("Cin Yerli Uretim", 2),
    "semiconductor self-sufficiency": ("Cin Yerli Cip", 3),
    "smic":              ("SMIC Cin Foundry", 2),
    "yangtze memory":    ("YMTC", 2),

    # Tedarik zinciri (supply chain)
    "supply chain disruption": ("Tedarik Zinciri Kirilmasi", 3),
    "supply chain shortage":   ("Tedarik Zinciri Kithgi", 3),
    "chip shortage":           ("Cip Kitligi", 3),
    "wafer shortage":          ("Wafer Kitligi", 3),
    "logistics":               ("Lojistik", 1),
    "supplier":                ("Tedarikci", 1),
    "bottleneck":              ("Tedarik Sikistirma", 2),
    "reshoring":               ("Reshoring (geri tasima)", 2),
    "nearshoring":             ("Nearshoring", 2),
    "onshoring":               ("Onshoring", 2),

    # Litografi / fab (ASML, EUV)
    "euv lithography":   ("EUV Litografi", 3),
    "high-na euv":       ("High-NA EUV", 3),
    "asml":              ("ASML", 2),
    "extreme ultraviolet": ("EUV Atilim", 3),
    "duv":               ("DUV Litografi", 2),

    # Kuantum / fotonik tekno haber
    "quantum advantage": ("Kuantum Atilim", 3),
    "logical qubit":     ("Mantiksal Qubit", 3),
    "error correction":  ("Kuantum Hata Duzeltme", 2),
    "trapped ion":       ("Iyon Tuzagi", 2),
    "photonic":          ("Fotonik", 2),
    "quantum supremacy": ("Kuantum Ustunluk", 3),

    # Ureticilik / fabrika
    "new fab":           ("Yeni Fabrika", 3),
    "fab opening":       ("Fab Acilisi", 3),
    "capacity expansion":("Kapasite Genisleme", 2),
    "wafer supply":      ("Wafer Tedariki", 2),
    "200mm":             ("200mm Wafer Atilim", 3),
    "300mm":             ("300mm Wafer", 2),

    # Post-Quantum Cryptography (SEALSQ / LAES odagi)
    "post-quantum":      ("Post-Quantum Cryptography", 3),
    "post quantum":      ("Post-Quantum Cryptography", 3),
    "pqc":               ("PQC", 3),
    "quantum-safe":      ("Kuantum-Guvenli", 3),
    "quantum safe":      ("Kuantum-Guvenli", 3),
    "crystals-kyber":    ("NIST PQC Algoritmasi (Kyber)", 3),
    "crystals-dilithium":("NIST PQC Algoritmasi (Dilithium)", 3),
    "kyber":             ("Kyber PQC", 2),
    "dilithium":         ("Dilithium PQC", 2),
    "sphincs":           ("SPHINCS+ PQC", 2),
    "falcon":            ("FALCON PQC", 2),
    "fips 203":          ("FIPS 203 (ML-KEM)", 3),
    "fips 204":          ("FIPS 204 (ML-DSA)", 3),
    "fips 205":          ("FIPS 205 (SLH-DSA)", 3),
    "secure element":    ("Secure Element IP", 3),
    "vaultitrust":       ("SEALSQ VaultiTrust", 3),
    "wisekey":           ("WISeKey (SEALSQ ana sirket)", 2),
    "matter protocol":   ("Matter Protocol (IoT)", 2),
    "risc-v security":   ("RISC-V Guvenlik", 2),
    "q-day":             ("Q-Day (Kuantum Sifre Kirma Gunu)", 3),
    "harvest now":       ("Harvest Now Decrypt Later (HNDL)", 3),
    "iot security":      ("IoT Guvenlik", 2),
    "cnsa 2":            ("NSA CNSA 2.0 PQC Mandate", 3),
    "nsm-10":            ("US NSM-10 PQC Mandate", 3),

    # Kontratlar / kamu desteği
    "dod contract":      ("Savunma Kontrati (DoD)", 3),
    "darpa":             ("DARPA Kontrati", 3),
    "nasa contract":     ("NASA Kontrati", 2),
    "defense contract":  ("Savunma Kontrati", 3),
    "subsidy":           ("Devlet Tesviki", 2),
    "grant":             ("Hibe", 2),
    "ipcei":             ("AB IPCEI Cip Plani", 2),
}


def scan_text(text: str) -> list[dict]:
    """Bir haber metnindeki kritik terimleri dondurur."""
    if not text:
        return []
    low = text.lower()
    hits = []
    seen = set()
    for term, (label, weight) in CRITICAL_TERMS.items():
        if term in low and label not in seen:
            seen.add(label)
            hits.append({"term": term, "label": label, "weight": weight})
    return hits


def annotate_news(news_items: list[dict]) -> list[dict]:
    """
    Her habere 'critical' alanini ekler.
    {title, summary, sentiment, ...} -> aynisi + {'critical': [...], 'is_critical': bool}
    """
    annotated = []
    for item in news_items or []:
        text = f"{item.get('title','')} {item.get('summary','')}"
        hits = scan_text(text)
        item = dict(item)
        item["critical"] = hits
        item["is_critical"] = any(h["weight"] >= 3 for h in hits)
        annotated.append(item)
    return annotated


def critical_summary(annotated: list[dict]) -> dict:
    """Tum haberlerden kritik terim sayilari."""
    counts: dict[str, int] = {}
    total_critical = 0
    examples: dict[str, str] = {}
    for item in annotated:
        if item.get("is_critical"):
            total_critical += 1
        for h in item.get("critical", []):
            counts[h["label"]] = counts.get(h["label"], 0) + 1
            if h["label"] not in examples:
                examples[h["label"]] = item.get("title", "")[:120]
    # Onem agirligi siralamasi
    ordered = sorted(counts.items(), key=lambda x: -x[1])
    return {
        "total_critical": total_critical,
        "categories": ordered,
        "examples": examples,
    }
