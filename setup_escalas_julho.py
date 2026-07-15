# -*- coding: utf-8 -*-
"""Importa as escalas médicas de JULHO/2026 (Ofício de 18/06/2026).
Rodar no Railway Console:  python /app/setup_escalas_julho.py
"""
import sys
sys.path.insert(0, "/app/app")

from app import app
from models import db, EscalaMedica

COMP = "202607"
OBS  = "NÃO MARCAR PACIENTES DE REFERENCIADO"
OBS5 = "A PARTIR DE 05 ANOS · " + OBS

DIAS_LONGO = "1,2,3,7,8,9,10,14,15,16,17,21,22,23,24,28,29,30,31"

ESCALAS = [
    # ── DR. WERQUITON FERREIRA FILHO — Exames / MANHÃ ──
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "6,13,20,27", "Manhã", "07:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "6,13,20,27", "Manhã", "09:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "RETINOGRAFIA COLORIDA", DIAS_LONGO, "Manhã", "07:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "PAQUIMETRIA",           DIAS_LONGO, "Manhã", "08:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "TOPOGRAFIA CORNEANA",   DIAS_LONGO, "Manhã", "09:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "BIOMETRIA",             DIAS_LONGO, "Manhã", "10:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "MICROSCOPIA ESPECULAR", DIAS_LONGO, "Manhã", "11:00", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "BIOMETRIA",             "11", "Manhã", "07:30", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "MICROSCOPIA ESPECULAR", "18", "Manhã", "08:00", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "TOPOGRAFIA CORNEANA",   "25", "Manhã", "07:30", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "RETINOGRAFIA COLORIDA", "4",  "Manhã", "07:30", 50, OBS),
    ("WERQUITON FERREIRA FILHO", "PAQUIMETRIA",           "4",  "Manhã", "08:00", 50, OBS),

    # ── DR. WERQUITON FERREIRA FILHO — Exames / TARDE ──
    ("WERQUITON FERREIRA FILHO", "CAMPIMETRIA COMPUTADORIZADA", "6,13,20,27", "Tarde", "12:00", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "RETINOGRAFIA COLORIDA", DIAS_LONGO, "Tarde", "13:00", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "PAQUIMETRIA",           DIAS_LONGO, "Tarde", "13:30", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "TOPOGRAFIA CORNEANA",   DIAS_LONGO, "Tarde", "14:00", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "BIOMETRIA",             DIAS_LONGO, "Tarde", "15:00", 10, OBS),
    ("WERQUITON FERREIRA FILHO", "MICROSCOPIA ESPECULAR", DIAS_LONGO, "Tarde", "15:30", 10, OBS),

    # ── DRA. CARLA AGUIAR DE SOUSA REZENDE — Consulta Oftalmológica ──
    # Dias "cheios": 1,6,8,15,17,22,24,29,31 · Dias "reduzidos": 2,3,7,9,10,13,14,16,21,23,28,30
    # Dias especiais: 11,18,25 (só manhã) · 20,27 (reforçados)
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,2,3,6,7,8,9,10,11,13,14,15,16,17,21,22,23,24,28,29,30,31", "Manhã", "08:00", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "18,20,25,27", "Manhã", "08:00", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,2,3,6,7,8,9,10,11,13,14,15,16,17,21,22,23,24,28,29,30,31", "Manhã", "08:30", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "18,20,25,27", "Manhã", "08:30", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,6,8,11,15,17,18,20,22,24,25,27,29,31", "Manhã", "09:00", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "2,3,7,9,10,13,14,16,21,23,28,30", "Manhã", "09:00", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,6,8,15,17,20,22,24,27,29,31", "Manhã", "10:00", 20, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "18,25", "Manhã", "10:00", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "2,3,7,9,10,11,13,14,16,21,23,28,30", "Manhã", "10:00", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,6,8,15,17,20,22,24,27,29,31", "Manhã", "11:00", 20, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "2,3,7,9,10,13,14,16,21,23,28,30", "Manhã", "11:00", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,6,8,15,17,20,22,24,27,29,31", "Tarde", "12:00", 20, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "2,3,7,9,10,13,14,16,21,23,28,30", "Tarde", "12:00", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,6,8,15,17,20,22,24,27,29,31", "Tarde", "14:00", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "2,3,7,9,10,13,14,16,21,23,28,30", "Tarde", "14:00", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,2,3,6,7,8,9,10,13,14,15,16,17,21,22,23,24,28,29,30,31", "Tarde", "14:30", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "20,27", "Tarde", "14:30", 10, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "1,2,3,6,7,8,9,10,13,14,15,16,17,21,22,23,24,28,29,30,31", "Tarde", "15:00", 5, OBS5),
    ("CARLA AGUIAR DE SOUSA REZENDE", "CONSULTA OFTALMOLÓGICA", "20,27", "Tarde", "15:00", 10, OBS5),

    # ── DR. RONALDO REZENDE JORDÃO NETO — Mapeamento de Retina ──
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "3,17", "Manhã", "07:00", 5, OBS),
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "3,17", "Manhã", "09:00", 10, OBS),
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "3,10,17", "Tarde", "12:30", 5, OBS),
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "3,17", "Tarde", "14:00", 5, OBS),
    ("RONALDO REZENDE JORDÃO NETO", "MAPEAMENTO DE RETINA", "10", "Tarde", "14:00", 10, OBS),
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
