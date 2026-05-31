"""
engineering_notes.py - Hisse bazli MUHENDISLIK NOTU (kullanici talebi v8).

Investor Executive Summary'in altinda gosterilen teknik yorum:
  - Sabit baz notlar (donanim/teknoloji aciklamasi)
  - Dinamik eklemeler (master score modifier'larina, overlay'lere bagli)
  - Kritik esik bilgisi (haberden cekilebilecek tetikleyici)
"""
from __future__ import annotations

# Hisse -> sabit muhendislik notu (teknoloji + competitive advantage)
BASE_NOTE = {
    "NVTS": (
        "GaN (Gallium Nitride) bant araligi ~3.4 eV, silikona gore ~10x "
        "yuksek elektron hareketliligi - 48V rack-scale guc kaynaginda "
        "anahtarlama kayiplarini %30+ azaltir. GaNFast monolitik IC + "
        "GaNSense akim algılama mimarisi Tier-1 OEM AEC-Q100 sertifikasyon "
        "esigine yaklasti."
    ),
    "LAES": (
        "SEALSQ Corp (WISeKey iştiraki). NIST CRYSTALS-Kyber/Dilithium PQC "
        "algoritmalarini QS7001 Secure Element ASIC'inde donanim-seviyesinde "
        "implemente eder. Common Criteria EAL5+ sertifikasi + RISC-V Trusted "
        "Execution Environment ile post-quantum tehditlere karsi hardware "
        "root-of-trust saglar."
    ),
    "AXTI": (
        "InP (Indium Phosphide) ve GaAs alttas (substrate) ureticisi. "
        "Silicon Photonics 800G/1.6T transceiver'lar ve 6G mmWave/THz radyo "
        "icin kritik. Cin operasyonlari nedeniyle Galyum/Germanyum ihracat "
        "lisansi onemli risk. IQE plc + Sumitomo Electric ana rakipler."
    ),
    "IONQ": (
        "Iyon-tuzakli (trapped-ion) kuantum bilgisayar - Baryum kübitleri ile "
        "uzun koherans suresi (>1s) ve yuksek 2-kübit fidelity (>%99.9). "
        "Hedef AQ 64 (Algorithmic Qubit) ile fault-tolerant kuantum hesaplama "
        "esigine yaklasmak. Oda sicakligi operasyonu uzun vadeli ticarilesme "
        "anahtari."
    ),
    "RGTI": (
        "Superconducting transmon kübit (Josephson junction) mimarisi. "
        "<20 mK dilution refrigerator gerektirir. 84-kübit Ankaa-2 isleme "
        "uniti + multi-chip modul scaling ile 1000+ kübit hedefi. "
        "IONQ'ya gore farkli teknoloji - sepet halinde degerlendirilir."
    ),
    "ATOM": (
        "Atomera MST (Mears Silicon Technology) - silikon kristal kafesin "
        "monolayer-skala dopant kontrol katmani. Mevcut foundry uretim "
        "akisina <1 mask step ile entegre olur. Transistor performansini "
        "%20-30 artirip kaçak akimi %40 azaltir. JDA (Joint Development "
        "Agreement) imzalanmasi 'Royalty per Wafer' modelini tetikler."
    ),
    "WOLF": (
        "Wolfspeed - dunyanin lider SiC (Silicon Carbide) wafer ureticisi. "
        "200mm SiC kristal cekme teknolojisi ile maliyet/wafer rekabet "
        "avantaji saglar. Mohawk Valley fab dunyada ilk 200mm SiC tesisi. "
        "EV traction inverter ve onboard charger'da silikona gore %40 hacim "
        "azaltma."
    ),
    "ASML": (
        "EUV (13.5 nm) litografi makineleri tekelinde. High-NA EUV "
        "(NA=0.55) ile 2nm ve altinda single-exposure pattering. TSM/Intel/"
        "Samsung'a yillik <50 makine teslimati, makine basina ~$350M. "
        "Cin'e ihracat kisitlamasi en buyuk jeopolitik risk."
    ),
    "NVDA": (
        "AI accelerator dominansi - CUDA software stack moat'i + Blackwell "
        "GB200 rack-scale GPU + NVLink networking. Hyperscaler capex'inin "
        "%60-70'ini cekiyor. AMD MI300 + AWS Trainium tek ciddi rakipler."
    ),
    "INDI": (
        "Autonomous vehicle SoC - DSP + Vision + Radar pipeline tek chip'te. "
        "Tesla FSD HW4 / Mobileye EyeQ Ultra rakibi. Tier-1 OEM design win'i "
        "tek katalist - L3+ otonom regulasyon hizina bagli."
    ),
    "QBTS": (
        "D-Wave - kuantum annealing (gate-model degil). Combinatorial "
        "optimizasyon, lojistik ve malzeme simulasyonu icin Advantage "
        "sistemleri. IONQ/RGTI kuantum sepetini fiziksel olarak tamamlar."
    ),
    "CRDO": (
        "Active Electrical Cable (AEC) - AI rack icinde bakirdan optige "
        "gecis. 800G/1.6T hyperscale interconnect. NVDA Blackwell cluster "
        "bandwidth darbogazinin cozumu - NVTS power semi ile ayni AI DC "
        "build-out ruzgarindan faydalanir."
    ),
    "ALAB": (
        "PCIe Gen6 + CXL 3.0 retimer - AI server'da CPU-GPU-NIC arasi "
        "sinyal butunlugu. Aries Smart DSP Platform hyperscaler design-win "
        "modeli. NVLink/CXL fabric scaling'in kritik katmani."
    ),
    "AEHR": (
        "Wafer-level burn-in / test - SiC ve GaN uretim ramp'inde zorunlu "
        "kalite adimi. WOLF + NVTS uretim hacmi arttikca AEHR kapasite "
        "satar ('pickaxe play'). Fox XP + Sonoma sistemleri."
    ),
    "POET": (
        "Monolitik Silicon Photonics - optik engine + laser kaynagi entegre "
        "ASIC. 800G/1.6T datacenter optical interconnect. ATOM-benzeri "
        "JDA/lisanslama modeli potansiyeli. AXTI InP altyapisini tamamlar."
    ),
    "AVGO": (
        "Custom AI ASIC (Google TPU ortagi) + yuksek-marjli networking "
        "switch ASIC. NVDA'nin en gercekci rakibi hyperscaler XPU'da. "
        "VMware + AI software stack ile entegre moat."
    ),
    "MRVL": (
        "Custom AI silicon (AWS Trainium ortagi) + datacenter electro-optics "
        "+ automotive ethernet. AVGO ile ayni 'custom XPU' temasi, daha "
        "ucuz degerleme profili."
    ),
    "VRT": (
        "AI veri merkezi guc + sogutma altyapisi. Rack power density "
        "artisi (48V, liquid cooling) hyperscaler capex'in dolayli "
        "1. derece beneficiary'si. NVTS chip-level, VRT system-level."
    ),
    "MU": (
        "HBM3E (High Bandwidth Memory) - NVDA Blackwell GPU yigininin "
        "olmazsa olmazi. AI capex -> HBM allocation -> MU/SK Hynix "
        "duopoly. Supply constraint = pricing power."
    ),
    "LSCC": (
        "Dusuk guc FPGA - edge AI inference, industrial IoT, automotive "
        "sensor fusion. NVIDIA GPU'dan farkli segment; tamamlayici edge "
        "compute. Nexus platform AI acceleration."
    ),
    "ARM": (
        "CPU IP lisanslama - her cihaza royalty. v9 + Neoverse V-series "
        "datacenter AI CPU. ATOM ile ayni 'royalty-per-unit' modeli. "
        "RISC-V tehdidi uzun vadeli risk."
    ),
    "ARQQ": (
        "Post-Quantum Encryption SaaS (symmetric key). LAES'in yazilim "
        "eslenigi - LAES=HW root-of-trust, ARQQ=cloud encryption. "
        "Government/enterprise mandate katalisti."
    ),
    "PLTR": (
        "Enterprise + savunma AI analytics platformu (AIP). Donanim degil "
        "yazilim - ama AI capex dongusunun 'uygulama katmani'. DoD "
        "kontratlari ve Fortune 500 AIP deployment."
    ),
    "AMBA": (
        "Edge AI vision SoC - otonom surus kamera pipeline. INDI'nin "
        "direkt rakibi. CVflow NPU + ISP entegre. Tier-1 automotive "
        "design-win odakli."
    ),
    "SMCI": (
        "AI server OEM - NVDA GPU'lari rack-scale sistemlere paketler. "
        "Liquid cooling + yuksek yogunluk. VRT ile ayni AI DC build-out "
        "temasi; daha volatil, muhasebe riski tarihsel."
    ),
}

# Hisse -> 'Kritik Esik (Haberden Cek)' - Investor Overview kolonu
# Bu metin haberden cikan kritik tetikleyiciyi raporlar.
CRITICAL_THRESHOLD = {
    "NVTS": "Tier-1 OEM (Tesla/VW/Hyundai/Stellantis) ana tedarik anlasmasi",
    "LAES": "NIST CRYSTALS-Kyber/Dilithium QS7001'e donanim entegrasyonu + "
              "Common Criteria EAL5+ sertifikasi",
    "AXTI": "Cin Galyum/Germanyum ihracat lisansi degisikligi + 6G mmWave "
              "transceiver design win",
    "IONQ": "AQ 64 (Algorithmic Qubit) baski testi + barium qubit "
              "guvenilirligi",
    "RGTI": "1000+ kübit roadmap doğrulamasi + error correction breakthrough",
    "ATOM": "Tier-1 Foundry (Intel/TSMC/Samsung) ile imzalı JDA (Joint "
             "Development Agreement)",
    "WOLF": "Mohawk Valley 200mm SiC yield orani >%70 + EV OEM hacim "
              "rampasi",
    "ASML": "High-NA EUV teslimat takvimi + Cin ihracat statusu",
    "NVDA": "Hyperscaler capex (MSFT/META/GOOG) buyume + Blackwell rack-scale",
    "INDI": "Tier-1 OEM L3+ FSD design win + AEC-Q100 sertifikasyonu",
    "QBTS": "Advantage2 cloud quantum + Fortune 500 enterprise contract",
    "CRDO": "800G/1.6T AEC hyperscaler (NVDA/META/MSFT) design win",
    "ALAB": "PCIe Gen6 / CXL 3.0 retimer hyperscaler volume ramp",
    "AEHR": "SiC/GaN wafer-level burn-in capacity order + yield tool",
    "POET": "800G optical engine JDA + foundry/light-source partner",
    "AVGO": "Custom XPU ASIC volume (Google/Meta) + AI networking switch",
    "MRVL": "Custom AI silicon design win (AWS/cloud) + electro-optics",
    "VRT": "Hyperscaler liquid cooling + 48V rack power capex order",
    "MU": "HBM3E NVDA Blackwell allocation + multi-year supply deal",
    "LSCC": "Edge AI FPGA automotive/industrial design win ramp",
    "ARM": "v9 AI CPU + Neoverse datacenter licensing volume",
    "ARQQ": "Government/enterprise NIST PQC software mandate contract",
    "PLTR": "DoD AI platform contract + AIP enterprise deployment scale",
    "AMBA": "Tier-1 automotive vision SoC design win + L3+ sertifikasyon",
    "SMCI": "NVDA GB200 rack-scale server volume shipment backlog",
}


def get_base_engineering_note(ticker: str) -> str:
    return BASE_NOTE.get(ticker.upper(), "")


def get_critical_threshold(ticker: str) -> str:
    return CRITICAL_THRESHOLD.get(ticker.upper(), "-")


def get_engineering_note(ticker: str, result: dict | None = None) -> dict:
    """
    Tam muhendislik notu - sabit baz + dinamik durum.

    Returns:
      {
        ticker, base_note, dynamic_status, critical_threshold,
        full_text
      }
    """
    t = ticker.upper()
    base = BASE_NOTE.get(t, "")
    crit = CRITICAL_THRESHOLD.get(t, "-")

    dyn = []
    if result is not None:
        # Strategic overlay durumu
        so = (result.get("strategic_overlay") or {})
        labels = so.get("labels", [])
        details = so.get("details", {})

        if t == "NVTS":
            if details.get("tier1_threshold_crossed"):
                oems = details.get("tier1_oems", [])
                dyn.append("🟢 Tier-1 OEM esigi GECILDI" +
                              (f" ({', '.join(oems)})" if oems else ""))
            else:
                dyn.append("⏳ Tier-1 OEM tedarik haberi henuz bekleniyor.")
            if details.get("dc_power_active"):
                dyn.append("🖥️ NVDA Blackwell/Rubin 48V power haberi aktif "
                              "- AI DC ruzgari NVTS'e doğrudan etki ediyor.")

        elif t == "LAES":
            if details.get("nist_integration"):
                dyn.append("🔐 NIST PQC HW entegrasyonu DOĞRULANDI "
                              "(CRYSTALS-Kyber/Dilithium silicon). "
                              "Q-Day katalisti hazır.")
            if details.get("demand_spike_active"):
                dyn.append("⚡ Q-Day demand spike aktif - cybersec CAPEX "
                              "rüzgarı.")
            elif not details.get("nist_integration"):
                dyn.append("⏳ NIST PQC HW silicon entegrasyon onayi "
                              "bekleniyor.")

        elif t == "ATOM":
            if result.get("atom_exponential_mode"):
                dyn.append("📜 Foundry JDA kabulu DOĞRULANDI - EXPONENTIAL "
                              "CAGR modu aktif (royalty-per-wafer modeli).")
            else:
                dyn.append("⏳ Foundry JDA imzasi (Intel/TSMC/Samsung) "
                              "bekleniyor.")

        elif t == "IONQ":
            if (result.get("vision") or {}).get("vision_bonus", 0) >= 15:
                dyn.append("🎯 AQ kübit roadmap'inde ilerleme tespit edildi.")

        elif t == "AXTI":
            geo = (result.get("geo_risk") or {})
            if geo.get("critical_alert"):
                dyn.append("🚨 Cin Galyum/Germanyum ihracat kontrolu aktif "
                              "risk - lisans degişikliği yakindan izle.")
            cb = (result.get("competitor_benchmark") or {})
            if cb.get("bonus", 0) >= 5:
                dyn.append(f"🥊 Rakiplerden ({', '.join(cb.get('competitors', []))}) "
                              f"goreceli guc {cb.get('relative_strength_pp', 0):+.0f}pp.")

        # Moonshot J-Curve sinyali (tum moonshot adaylari icin)
        m = (result.get("moonshot") or {})
        if m.get("master_bonus", 0) >= 12:
            rev = m.get("revenue_yoy_pct")
            rd = m.get("rd_yoy_pct")
            if rev is not None and rd is not None:
                dyn.append(f"🚀 J-Curve onayli: Revenue YoY %{rev:+.0f} + "
                              f"R&D YoY %{rd:+.0f} paralel buyume.")

        # Cash runway
        cr = (result.get("cash_runway") or {})
        if cr.get("is_unsustainable"):
            dyn.append(f"⛔ Finansal surdurulebilirlik riski - cash runway "
                          f"{cr.get('runway_months', 0):.0f} ay.")

    full = base + ("\n\n" + "\n".join(dyn) if dyn else "")

    return {
        "ticker": t,
        "base_note": base,
        "dynamic_status": dyn,
        "critical_threshold": crit,
        "full_text": full,
    }
