import { render } from 'preact';
import './stil/jetonlar.css';
import './stil/temel.css';
import { izinVarsaKonumuAl } from './uygulama/durum';
import { rotayiIzle } from './uygulama/rota';
import { Uygulama } from './uygulama/Uygulama';
import { baglantiyiIzle, veriyiYukle } from './veri/yukle';
import { saatiCalistir } from './zaman/saat';

rotayiIzle();
baglantiyiIzle();
saatiCalistir();
veriyiYukle();
izinVarsaKonumuAl();

const kok = document.getElementById('uygulama');
if (kok) render(<Uygulama />, kok);
