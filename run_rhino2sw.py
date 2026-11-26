"""Punto di ingresso per PyInstaller e per l'avvio da sorgente: python run_rhino2sw.py"""
import sys

from rhino2sw.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
