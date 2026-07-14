# -*- coding: utf-8 -*-
"""Importa as escalas médicas de AGOSTO/2026 (Ofício de 14/07/2026).
Rodar no Railway Console:  cd /app/app && python /app/setup_escalas_agosto.py
"""
import sys
sys.path.insert(0, "/app/app")

from app import app
from models import db, EscalaMedica

COMP = "202608"
OBS  = "NÃO MARCAR PACIENTES DE REFERENCIADO"

ESCALAS = [
    # ── DR. RONALDO REZENDE JORDÃO NETO — Mapeamento de Retina ──
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "7", "Manhã", "07:30", 25, OBS),
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "7", "Manhã", "09:00", 25, OBS),

    # ── DR. WERQUITON FERREIRA FILHO — Exames / MANHÃ ──
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "3,10,17,24,31", "Manhã", "07:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "3,10,17,24,31", "Manhã", "09:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "TOPOGRAFIA CORNEANA",   "4,7,11,14,18,21,25,28", "Manhã", "07:30", 20, OBS),
    ("WERQUITON FERREIRA FILHO", "BIOMETRIA",             "4,7,11,14,18,21,25,28", "Manhã", "09:00", 20, OBS),
    ("WERQUITON FERREIRA FILHO", "MICROSCOPIA ESPECULAR", "4,7,11,14,18,21,25,28", "Manhã", "09:30", 20, OBS),
    ("WERQUITON FERREIRA FILHO", "TOPOGRAFIA CORNEANA",   "5,6,12,13,19,20,26,27", "Manhã", "08:00", 5, OBS),
    ("WERQUITON FERREIRA FILHO", "BIOMETRIA",             "5,6,12,13,19,20,26,27", "Manhã", "08:30", 5, OBS),
    ("WERQUITON FERREIRA FILHO", "MICROSCOPIA ESPECULAR", "5,6,12,13,19,20,26,27", "Manhã", "09:00", 5, OBS),
    ("WERQUITON FERREIRA FILHO", "BIOMETRIA",             "22", "Manhã", "07:30", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "1", "Manhã", "07:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "MICROSCOPIA ESPECULAR", "29", "Manhã", "08:00", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "TOPOGRAFIA CORNEANA",   "8",  "Manhã", "07:30", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "RETINOGRAFIA COLORIDA", "15", "Manhã", "07:30", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "PAQUIMETRIA",           "15", "Manhã", "08:00", 50, OBS),

    # ── DR. WERQUITON FERREIRA FILHO — Exames / TARDE ──
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "3,10,17,24,31", "Tarde", "12:00", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "RETINOGRAFIA COLORIDA", "4,7,11,14,18,21,25,28", "Tarde", "14:00", 20, OBS),
    ("WERQUITON FERREIRA FILHO", "PAQUIMETRIA",           "4,7,11,14,18,21,25,28", "Tarde", "14:30", 20, OBS),
    ("WERQUITON FERREIRA FILHO", "RETINOGRAFIA COLORIDA", "5,6,12,13,19,20,26,27", "Tarde", "14:00", 5, OBS),
    ("WERQUITON FERREIRA FILHO", "PAQUIMETRIA",           "5,6,12,13,19,20,26,27", "Tarde", "14:30", 5, OBS),

    # ── DRA. CARLA AGUIAR DE SOUSA REZENDE — Consulta Oftalmológica ──
    # MARCAR PACIENTES A PARTIR DE 05 ANOS
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,8,15,22,29",            "Manhã", "08:00", 15, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,8,15,22,29",            "Manhã", "09:00", 15, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "3,5,10,12,17,19,24,26,31","Manhã", "08:00", 20, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "4,7,11,14,18,21,25,28",   "Manhã", "08:00", 25, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "3,4,5,6,7,10,11,12,13,14,17,18,19,20,21,24,25,26,27,28,31", "Manhã", "09:00", 25, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "3,5,10,12,17,19,24,26,31","Manhã", "10:00", 25, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "3,4,5,6,7,10,11,12,13,14,17,18,19,20,21,24,25,26,27,28,31", "Tarde", "13:00", 25, "A PARTIR DE 05 ANOS · " + OBS),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "3,4,5,7,10,11,12,14,17,18,19,21,24,25,26,28,31", "Tarde", "14:00", 25, "A PARTIR DE 05 ANOS · " + OBS),
]

with app.app_context():
    db.create_all()
    ja = EscalaMedica.query.filter_by(competencia=COMP).count()
    if ja:
        print(f"Já existem {ja} escalas em {COMP}. Apagando para reimportar...")
        EscalaMedica.query.filter_by(competencia=COMP).delete()
        db.session.commit()

    n = 0
    for medico, proc, dias, turno, hora, vagas, obs in ESCALAS:
        db.session.add(EscalaMedica(
            competencia=COMP, medico=medico, procedimento=proc,
            dias=dias, turno=turno, horario=hora, qtd_vagas=vagas, observacao=obs,
        ))
        n += 1
    db.session.commit()
    print(f"OK — {n} escalas de {COMP} importadas.")
