import { metin } from '../metin/metinler';

// Harfler çizgiyle çizilir: yazı tipine bağlı değil, rengini `currentColor` ile alır.
export function Logo() {
  return (
    <a class="logo" href="#/">
      <span class="gorsel-gizli">{metin.marka.anaSayfa}</span>
      <span class="p-levha" aria-hidden="true">
        P
      </span>
      <svg class="kelime-isareti" viewBox="-2 0 70 24" aria-hidden="true" focusable="false">
        <path d="M0 4l5 8 5-8M5 12v8" />
        <path d="M13 15h9a4.5 4.5 0 1 0-1.3 3.2" />
        <path d="M25.5 20V10.5M25.5 14.5a5 5 0 0 1 5-4" />
        <path d="M33.5 4l5.5 16 5.5-16" />
        <circle cx="51.5" cy="15" r="4.5" />
        <path d="M56 10.5V20" />
        <path d="M59.5 20V10.5M59.5 14.5a5 5 0 0 1 5-4" />
      </svg>
    </a>
  );
}
