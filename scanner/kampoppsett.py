"""Interactive configuration of away sections for each checkout event."""
import argparse
from pathlib import Path
from match_config import ROOT,SEATS,normalize_locked,load_locked,save_locked
from publication import event_key


def main():
    ap=argparse.ArgumentParser(description='Bekreft bortefelt per RBK-kamp')
    ap.add_argument('--url',default='')
    ap.add_argument('--locked',default=None,help='Komma-separerte FELT; tom streng fjerner alle')
    ap.add_argument('--confirm',action='store_true')
    args=ap.parse_args()
    try:
        url=args.url or input('Lim inn full RBK checkout-URL: ').strip()
        event_key(url)
        current=load_locked(ROOT/'kampoppsett',url)
        print('\nKjente registrerte bortefelt:',', '.join(current) if current else 'Ingen')
        print('OBS: Kun felt som er dokumentert låst for ordinært salg skal legges til.')
        value=args.locked if args.locked is not None else input('Skriv 1–2 låste feltnavn (f.eks RB,SA), eller ENTER for ingen: ').strip()
        locked=normalize_locked(value)
        print('\nBekreftet bortefelt:', ', '.join(locked) or 'Ingen')
        print('Utelukket kapasitet:',sum(SEATS[s] for s in locked),'. Dette regnes IKKE som bekreftet solgt.')
        confirmed=args.confirm
        if not confirmed:
            confirmed=input('Skriv BEKREFT for å lagre dette kampoppsettet: ').strip()=='BEKREFT'
        if not confirmed:
            print('Avbrutt. Ingen endringer.');return 1
        path=save_locked(ROOT/'kampoppsett',url,locked,confirmed=True)
        print('Lagret:',path)
        print('Start nå Hurtigkart som normalt. Oppsettet leses automatisk for denne kamp-URL-en.')
        return 0
    except (ValueError,KeyboardInterrupt) as e:
        print('Ugyldig oppsett:',str(e));return 2

if __name__=='__main__':raise SystemExit(main())