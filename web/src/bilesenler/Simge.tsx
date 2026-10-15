import type { JSX } from 'preact';

export type SimgeAdi =
  | 'yer_var_olasi'
  | 'belirsiz'
  | 'dolu_olasi'
  | 'basit'
  | 'veri_yok'
  | 'olcum'
  | 'saat'
  | 'uyari'
  | 'hata'
  | 'konum'
  | 'ara'
  | 'menu'
  | 'geri'
  | 'disari';

// Her bandın kendi şekli var (daire, eşkenar dörtgen, kare): renk görülmese de ayırt edilir.
const cizimler: Record<SimgeAdi, JSX.Element> = {
  yer_var_olasi: (
    <>
      <circle cx="12" cy="12" r="10" class="simge-dolgu" />
      <path d="M7 12.5l3.2 3.2L17 9" class="simge-ic" />
    </>
  ),
  belirsiz: (
    <>
      <path d="M12 1.5L22.5 12 12 22.5 1.5 12z" class="simge-dolgu" />
      <path d="M7.5 13c1.5-2.4 3-2.4 4.5 0s3 2.4 4.5 0" class="simge-ic" />
    </>
  ),
  dolu_olasi: (
    <>
      <rect x="2.5" y="2.5" width="19" height="19" rx="3" class="simge-dolgu" />
      <path d="M8 8l8 8M16 8l-8 8" class="simge-ic" />
    </>
  ),
  basit: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" class="simge-cizgi" />
      <path
        d="M9.5 7.5v9h3.2a2.2 2.2 0 0 0 0-4.5H9.5h2.7a2.1 2.1 0 0 0 0-4.5z"
        class="simge-cizgi-ince"
      />
    </>
  ),
  veri_yok: (
    <>
      <circle cx="12" cy="12" r="9.5" class="simge-cizgi simge-kesikli" />
      <path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.6" class="simge-cizgi-ince" />
      <circle cx="12" cy="16.8" r="1.1" class="simge-nokta" />
    </>
  ),
  olcum: (
    <>
      <circle cx="12" cy="12" r="9.5" class="simge-cizgi" />
      <circle cx="12" cy="12" r="3.5" class="simge-nokta" />
    </>
  ),
  saat: (
    <>
      <circle cx="12" cy="13" r="8.5" class="simge-cizgi" />
      <path d="M12 8.5V13l3 2M9.5 2.5h5" class="simge-cizgi-ince" />
    </>
  ),
  uyari: (
    <>
      <path d="M12 2.5L22.5 21h-21z" class="simge-cizgi" />
      <path d="M12 9v5.5" class="simge-cizgi-ince" />
      <circle cx="12" cy="17.6" r="1.1" class="simge-nokta" />
    </>
  ),
  hata: (
    <>
      <circle cx="12" cy="12" r="9.5" class="simge-cizgi" />
      <path d="M12 7v6.5" class="simge-cizgi-ince" />
      <circle cx="12" cy="16.8" r="1.1" class="simge-nokta" />
    </>
  ),
  konum: (
    <>
      <circle cx="12" cy="12" r="7" class="simge-cizgi" />
      <circle cx="12" cy="12" r="2.6" class="simge-nokta" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" class="simge-cizgi-ince" />
    </>
  ),
  ara: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" class="simge-cizgi" />
      <path d="M15.5 15.5L21 21" class="simge-cizgi-ince" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" class="simge-cizgi-ince" />,
  geri: <path d="M15 5l-7 7 7 7" class="simge-cizgi-ince" />,
  disari: <path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6" class="simge-cizgi-ince" />,
};

export function Simge({ ad }: { ad: SimgeAdi }) {
  return (
    <svg class={`simge simge-${ad}`} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {cizimler[ad]}
    </svg>
  );
}
