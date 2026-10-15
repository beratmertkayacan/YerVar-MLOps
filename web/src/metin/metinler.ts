// Kullanıcıya görünen bütün metinler burada durur; ekran kodu metin yazmaz.
// Kural: bir sayı ya da saatin hemen ardına ek getirilmez ("08:05'te" değil, "saat 08:05").

export const metin = {
  marka: {
    ad: 'YerVar',
    anaSayfa: 'YerVar ana sayfa',
  },
  icerigeGec: 'İçeriğe geç',
  filigran: 'Prototip · sahte veri',
  sayfaBasligi: (sayfa: string) => `${sayfa} · YerVar`,

  gezinme: {
    etiket: 'Sayfalar',
    menu: 'Menü',
    harita: 'Harita',
    liste: 'Liste',
    hakkinda: 'Nasıl çalışır?',
  },

  arama: {
    etiket: 'Otopark ya da semt ara',
    yerTutucu: 'Nereye gidiyorsun?',
    sonucYok: 'Bu aramaya uyan otopark yok.',
    sonucSayisi: (n: number) => `${n} sonuç`,
  },

  konum: {
    kullan: 'Konumumu kullan',
    kisa: 'Konum',
    bekleniyor: 'Konum alınıyor…',
    yok: 'Yakındaki otoparkları görmek için konum izni ver ya da semt ara.',
    reddedildi: 'Konum izni verilmedi. Tarayıcı ayarlarından açabilir ya da semt arayabilirsin.',
    mesafe: (mesafe: string, dk: number) => `${mesafe} · yürüyerek yaklaşık ${dk} dk (kuş uçuşu)`,
    kisaMesafe: (mesafe: string) => `${mesafe} (kuş uçuşu)`,
    genisledi: '1 km içinde 3’ten az otopark var; arama alanını 2 km’ye genişlettik.',
    sonucYok: 'Konumunun 2 km çevresinde İSPARK otoparkı yok. Haritada başka bir yere bak.',
  },

  yukleme: {
    suruyor: 'Tahminler yükleniyor…',
    uzun: 'Sunucu uyanıyor, birkaç saniye sürebilir.',
  },

  veriCipi: (saat: string, yas: string) => `Veri ${saat} · ${yas}`,
  zaman: {
    azOnce: 'az önce',
    dakika: (dk: number) => `${dk} dk önce`,
    saat: (sa: number) => `${sa} sa önce`,
    saatDakika: (sa: number, dk: number) => `${sa} sa ${dk} dk önce`,
  },
  hedefSaat: (saat: string) => `${saat} için`,
  saatIcin: (saat: string) => `saat ${saat} için`,

  varis: {
    baslik: 'Ne zaman varacaksın?',
    simdi: 'Şimdi',
    simdiAciklama: 'Şimdi (son ölçüm)',
    secenek: (dk: number) => (dk < 60 ? `${dk} dk` : `${dk / 60} sa`),
  },

  bant: {
    yer_var_olasi: { kisa: 'Yer var olası', cumle: 'Büyük olasılıkla yer bulursun.' },
    belirsiz: { kisa: 'Belirsiz', cumle: 'Yer olabilir ama garanti değil.' },
    dolu_olasi: { kisa: 'Dolu olası', cumle: 'Büyük olasılıkla dolu olacak.' },
  },
  aralik: (alt: string, ust: string) => `Tahmini ${alt}–${ust} boş yer`,
  aralikKisa: (alt: string, ust: string) => `${alt}–${ust}`,
  aralikHesaplanmadi: (bos: string) => `~${bos} boş yer (aralık hesaplanmadı)`,
  bosYer: 'boş yer',
  bosYerSayi: (bos: string) => `${bos} boş yer`,
  doluNe: {
    soru: 'Dolu ne demek?',
    cevap:
      'Dolu: boş yer sayısı, kapasitenin %5’i ile 10’dan hangisi küçükse o sayıya ya da altına inmiş demek.',
  },
  siklik: {
    yaklasik: (bant: string, n: number) =>
      `Geçmişte tüm otoparklar için "${bant}" dediğimiz her 10 tahminden yaklaşık ${n} tanesinde otopark dolu çıktı.`,
    neredeyseHic: (bant: string) =>
      `Geçmişte tüm otoparklar için "${bant}" dediğimiz tahminlerde otopark neredeyse hiç dolu çıkmadı.`,
    neredeyseHepsi: (bant: string) =>
      `Geçmişte tüm otoparklar için "${bant}" dediğimiz tahminlerin neredeyse hepsinde otopark dolu çıktı.`,
  },
  egilim: {
    azaliyor: 'Doluyor: boş yer azalıyor.',
    artiyor: 'Boşalıyor: boş yer artıyor.',
  },

  basit: {
    kisa: 'Basit tahmin',
    bosYer: (bos: string) => `≈${bos} boş yer`,
    aciklama: 'Basit tahmin: son ölçümün süreceğini varsayıyoruz; olasılık hesaplanmadı.',
  },
  olcum: {
    kisa: 'Son ölçüm',
    satir: (saat: string, bos: string, kap: string) =>
      `Son ölçüm (saat ${saat}): ${bos} boş yer, kapasite ${kap}`,
    eski: (saat: string, yas: string, bos: string) =>
      `Son ölçüm ${saat} (${yas}): ${bos} boş yer. Güncel tahmin yok.`,
    saatinde: (saat: string) => `ölçüm saat ${saat}`,
    ne: (saat: string, yas: string) => `Son ölçüm ${saat} (${yas})`,
    guncelTahminYok: 'Güncel tahmin yok.',
  },

  kapsam: {
    veriYok: 'Veri yok',
    veriYokAciklama: 'Bu otopark şu an canlı veri göndermiyor; tahmin yapamıyoruz.',
    sebep: {
      canli_degil:
        'Bu otoparkın sayısı son günlerde neredeyse hiç değişmedi; sensörün çalışmadığını düşünüyoruz.',
      gozlem_yok: 'Son ölçümlerde bu otoparktan veri gelmedi.',
      kismen_canli:
        'Bu otoparkın verisi son günlerde zaman zaman donuktu; bu yüzden model yerine basit tahmin gösteriyoruz.',
      model_kiyasi_gecemedi:
        'Bu otoparkta modelimiz, şimdiki durumun süreceğini varsaymaktan daha iyi tahmin edemedi.',
      karnede_yok: 'Bu otopark için modeli henüz sınamadık; basit tahmin gösteriyoruz.',
      liste_disi: 'Son gün İSPARK listesinde yoktu; kapanmış ya da numarası değişmiş olabilir.',
    },
    sebepBilinmiyor: 'Bu otopark için güvenilir veri yok.',
    veriYokGrubu: (n: number) => `Veri yok (${n})`,
    gosterilmeyenler: (n: number) =>
      `Son gün İSPARK listesinde görünmeyen ${n} otopark gösterilmiyor.`,
    neden: 'Neden?',
  },

  serit: {
    gecikmis: (dk: number) => `Veriler ${dk} dk önce güncellendi; tahminler eskimiş olabilir.`,
    suresiDoldu: (saat: string) => `Tahminlerin süresi doldu. Son ölçüm saat ${saat}.`,
    cevrimdisi: 'Çevrimdışısın; son kaydedilen tahminler gösteriliyor.',
  },

  hata: {
    ulasilamiyor: 'Tahminlere şu an ulaşılamıyor.',
    tekrarDene: 'Tekrar dene',
    yeniSurum: 'Uygulamanın yeni sürümü var.',
    yenile: 'Yenile',
    bosVeri: 'Şu an gösterilecek otopark yok.',
  },

  harita: {
    etiket: 'Otopark haritası',
    yukleniyor: 'Harita yükleniyor…',
    yuklenemedi: 'Harita yüklenemedi. Listeden devam edebilirsin.',
    isaret: (ad: string, durum: string) => `${ad}: ${durum}`,
    isaretTahmin: (ad: string, bant: string, saat: string, alt: string, ust: string) =>
      `${ad}: ${bant}, saat ${saat} için tahmini ${alt} ile ${ust} arası boş yer.`,
    kapat: 'Kapat',
  },

  ana: {
    baslik: 'İstanbul otoparkları',
    sekmeler: 'Otopark listesi',
    onerilen: 'Önerilen',
    yakinimda: 'Yakınımda',
    tumu: 'Tüm liste',
  },

  detay: {
    geri: 'Harita',
    durumuGor: 'Durumu gör',
    zamanSeridi: 'Sonraki iki saat',
    yedekler: 'Yedek otoparklara bak',
    haritalardaAc: 'Haritalarda aç',
    bulunamadi: 'Bu numarayla bir otopark yok.',
    kapasite: (kap: string) => `${kap} araç`,
  },

  liste: {
    baslik: 'Liste',
    siralama: 'Sıralama',
    secenek: {
      onerilen: 'Önerilen',
      yakinlik: 'Yakınlık',
      olasilik: 'Yer bulma olasılığı',
    },
    yakinlikPasif: 'Yakınlığa göre sıralamak için konumunu kullan.',
  },

  hakkinda: {
    baslik: 'Nasıl çalışır?',
    nasil:
      'İSPARK verisi 5 dakikada bir toplanır; model 15, 30, 60 ve 120 dakika sonrasını tahmin eder; tahminler düzenli aralıkla yenilenir.',
    veriYasiBaslik: 'Veri yaşı',
    veriYasi: (esikDk: number) =>
      `Veri saati, İSPARK'tan gelen son ölçümün saatidir. O saatten bu yana geçen süre eşiği (şu an ${esikDk} dk) aşarsa tahminlerin eskimiş olabileceğini yazarız. Bütün tahminlerin hedef saati geçtiyse yalnızca son ölçümü gösteririz.`,
    gizlilikBaslik: 'Gizlilik',
    gizlilik:
      'Konumun ve hedefin yalnızca cihazında, bellekte kullanılır; bize gönderilmez ve saklanmaz.',
    harita:
      'Harita görüntüleri ve harita yazı tipleri harita sunucusundan (OpenFreeMap) iner; baktığın bölge o sunucuya iletilir. Konumun ve hedefin bize gönderilmez.',
    analitikYok: 'Analitik ve çerez yok.',
    gosterilmeyenBaslik: 'Gösterilmeyen otoparklar',
  },

  altBilgi:
    'Veri: İBB Açık Veri Portalı (İSPARK). İSPARK ile resmî bağlantısı yoktur. Tahminler bilgi amaçlıdır.',

  bulunamadi: {
    baslik: 'Sayfa bulunamadı',
    aciklama: 'Bu adreste bir sayfa yok.',
    donus: 'Ana sayfaya dön',
  },
};
