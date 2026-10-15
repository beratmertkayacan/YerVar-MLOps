import { describe, expect, it } from 'vitest';
import { ilceYaz, saatYaz, sayiYaz, yasYaz } from '../../src/metin/bicim';

const DK = 60_000;

describe('saat', () => {
  it('İstanbul saatiyle, 24 saat düzeninde yazar', () => {
    expect(saatYaz('2026-10-16T05:05:00Z')).toBe('08:05');
    expect(saatYaz('2026-10-16T12:30:00Z')).toBe('15:30');
  });

  it('İstanbul’da gece yarısını geçen saati doğru yazar', () => {
    expect(saatYaz('2026-10-16T21:30:00Z')).toBe('00:30');
  });
});

describe('veri yaşı', () => {
  const veri = '2026-10-16T05:05:00Z';
  const t = Date.parse(veri);

  it('bir dakikadan azsa "az önce" der', () => {
    expect(yasYaz(veri, t + 30_000)).toBe('az önce');
  });

  it('dakikayı aşağı yuvarlar', () => {
    expect(yasYaz(veri, t + 3 * DK + 59_000)).toBe('3 dk önce');
  });

  it('bir saati aşınca saat ve dakika yazar', () => {
    expect(yasYaz(veri, t + 65 * DK)).toBe('1 sa 5 dk önce');
    expect(yasYaz(veri, t + 120 * DK)).toBe('2 sa önce');
  });
});

describe('sayı', () => {
  it('binlikte nokta kullanır', () => {
    expect(sayiYaz(1250)).toBe('1.250');
    expect(sayiYaz(5022)).toBe('5.022');
  });
});

describe('Türkçe büyük ve küçük harf', () => {
  it('i ile İ, ı ile I eşleşir', () => {
    expect('istanbul'.toLocaleUpperCase('tr-TR')).toBe('İSTANBUL');
    expect('ılık'.toLocaleUpperCase('tr-TR')).toBe('ILIK');
  });

  it('ilçe adını baş harfi büyük yazar', () => {
    expect(ilceYaz('ŞİŞLİ')).toBe('Şişli');
    expect(ilceYaz('KADIKÖY')).toBe('Kadıköy');
    expect(ilceYaz('İNCİRLİ')).toBe('İncirli');
    expect(ilceYaz('IĞDIR')).toBe('Iğdır');
    expect(ilceYaz('EYÜPSULTAN')).toBe('Eyüpsultan');
  });

  it('birden çok sözcüklü adın her sözcüğünü büyük harfle başlatır', () => {
    expect(ilceYaz('YENİ İSKELE')).toBe('Yeni İskele');
  });
});
