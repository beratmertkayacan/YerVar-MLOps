import { metin } from './metinler';

const DAKIKA_MS = 60_000;

const saatBicimi = new Intl.DateTimeFormat('tr-TR', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: 'Europe/Istanbul',
});
const sayiBicimi = new Intl.NumberFormat('tr-TR');
const kmBicimi = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1 });

export function saatYaz(iso: string): string {
  return saatBicimi.format(new Date(iso));
}

export function sayiYaz(sayi: number): string {
  return sayiBicimi.format(sayi);
}

/** "650 m", "2,4 km": kısa mesafede 10 m'ye, uzunda 100 m'ye yuvarlanır. */
export function mesafeYaz(metre: number): string {
  if (metre < 1000) return `${Math.max(10, Math.round(metre / 10) * 10)} m`;
  return `${kmBicimi.format(Math.round(metre / 100) / 10)} km`;
}

export function dakikaFarki(oncekiIso: string, simdiMs: number): number {
  return Math.max(0, Math.floor((simdiMs - Date.parse(oncekiIso)) / DAKIKA_MS));
}

export function yasYaz(oncekiIso: string, simdiMs: number): string {
  const dakika = dakikaFarki(oncekiIso, simdiMs);
  if (dakika < 1) return metin.zaman.azOnce;
  if (dakika < 60) return metin.zaman.dakika(dakika);
  const saat = Math.floor(dakika / 60);
  const kalan = dakika % 60;
  return kalan === 0 ? metin.zaman.saat(saat) : metin.zaman.saatDakika(saat, kalan);
}

/** Kaynaktaki büyük harfli ilçe adını Türkçe kurala göre yazar: "ŞİŞLİ" → "Şişli". */
export function ilceYaz(ilce: string): string {
  return ilce
    .toLocaleLowerCase('tr-TR')
    .split(' ')
    .map((sozcuk) => sozcuk.charAt(0).toLocaleUpperCase('tr-TR') + sozcuk.slice(1))
    .join(' ');
}
