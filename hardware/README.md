# Placa de junção OpenDash (shield Arduino Mega 2560)

Placa que concentra **alimentação, proteção, entradas, saídas, CAN e GPS** entre o
carro e o Arduino Mega 2560. O Arduino continua sendo o cérebro; a placa só faz a
"cola" elétrica com proteção — nenhum sinal de 12 V chega direto aos pinos.

Este diretório é **gerado por código** (`generate.py`), então esquema, BOM e netlist
nunca ficam fora de sincronia com a pinagem oficial (`arduino/car_dash/config.h`).

```
hardware/
├── generate.py        gerador (somente biblioteca padrão do Python)
├── render_svg.py      SVG → PNG via GdkPixbuf (usa o python3 do sistema)
├── README.md          este arquivo
└── out/
    ├── schematic.svg  esquema elétrico completo
    ├── schematic.png  esquema em PNG
    ├── board.svg      desenho mecânico / placement (vista superior)
    ├── board.png      desenho em PNG
    ├── bom.csv        lista de materiais (referência, valor, encapsulamento)
    └── netlist.csv    todas as conexões net ↔ componente/pino
```

Regenerar:

```bash
python3 hardware/generate.py
python3 hardware/render_svg.py      # requer python3 com PyGObject/GdkPixbuf
```

## 1. Visão em blocos

| Bloco | O que faz |
|---|---|
| **1. Alimentação** | Entrada 12 V pós-chave → fusível 3 A → SS54 (polaridade reversa) → SMBJ18A (TVS) → buck LM2596S-5.0 → 5 V / 3 A |
| **2. Arduino Mega** | Shield encaixa nos headers; leva 5 V, GND, entradas/saídas e SPI/Serial1 |
| **3. CAN / OBD‑II** | MCP2515 + TJA1050 (SPI: CS D10, SCK D52, SI D51, SO D50); terminação 120 Ω com jumper |
| **4. GPS** | NEO‑6M/8M/M8N em 9600 baud no Serial1 (TX GPS→D19/RX1, RX GPS←D18/TX1 via R3 1 k) |
| **5. Entradas digitais** | 10 canais com R série 22 k, divisor 10 k, zener 5,1 V, 100 nF e jumper por canal (12 V **ou** chave-para-GND) |
| **6. Entradas analógicas** | A0/A1/A2 (0,5–4,5 V) com RC + zener; A1 com pull-up 1 k opcional; A3 com divisor 30 k/10 k |
| **7. Saídas** | Buzzer, LED de status e 2 relés (ventilador / A/C) por NPN + diodo de roda-livre |

## 2. Lista de materiais

A lista completa, com encapsulamento e descrição, está em
[`out/bom.csv`](out/bom.csv). Resumo:

- **Módulo**: Arduino Mega 2560; módulo MCP2515 (TJA1050); módulo GPS NEO‑6M/8M.
- **Alimentação**: LM2596S‑5.0, L1 33 µH/3 A, D3 SS34, D1 SS54, D2 SMBJ18A,
  F1 3 A, C1 470 µF/25 V, C3 220 µF/16 V, C2/C4 100 nF.
- **Entradas**: 10× R 22 k, 10× R 10 k, 10× zener 5,1 V, 10× 100 nF,
  10× jumper 3 pinos; bornes J6 (12 vias) e J7 (5 vias).
- **Analógicas**: R201/R202/R204 1 k, R203 1 k (pull-up), R205 30 k, R206 10 k,
  JP201, 4× zener 5,1 V, 4× 100 nF.
- **Saídas**: Q301–Q303, R301/R302/R304 1 k, R303/R305 10 k, D301/D302/D303,
  R310 1 k, LED1/D310, bornes J8/J9/J10/J11.
- **Conectores**: J2 (12 V), J3 (MCP2515), J4 (OBD‑II), J5 (GPS), J11 (5 V→Pi).
- **Placa**: face simples, **101,5 × 53,3 mm** (formato shield Mega).

## 3. Perfboard (DIY) ou placa fabricada?

**Perfboard / placa ilhada** — mais rápido e barato para uma unidade:

1. Corte uma placa de 101,5 × 53,3 mm e faça os 4 furos M3.
2. Encaixe os headers fêmea que vão receber o Mega (ou pinos macho, se a placa
   ficar embaixo) e marque os furos.
3. Siga a [`netlist.csv`](out/netlist.csv) **net a net**, usando fio de cobre
   esmaltado (0,5 mm) para as ligações longas e ilhas para os nós curtos.
4. Solda a malha de GND primeiro (é o nó com mais conexões).

**Placa fabricada** — melhor para várias unidades ou para o carro definitivo:

- O `board.svg` é **placement/mecânico**, não tem trilhas nem Gerbers.
- Para fabricar, use o esquema + netlist como entrada no KiCad/EasyEDA e gere
  Gerbers (ou peça a fabricação pelo esquema). Se quiser, o próximo passo natural
  é gerar o projeto KiCad a partir do `generate.py`.
- Fabricação caseira: transferência térmica ou UV da arte de cobre na face
  inferior + corrosão; componentes THT na face superior.

## 4. Ordem de montagem e solda

1. **Alimentação primeiro** (com a placa fora do carro): D1, D2, F1, C1, C3,
   buck U1 e LED de power. Teste as tensões antes de soldar qualquer outra coisa.
2. **MCU/headers**: soquetes/headers do Mega e o jumper `JP_VUSB`.
3. **CAN**: J3, R2, JP1, C6.
4. **GPS**: J5, R3, C7.
5. **Entradas digitais**: por canal — R série, R de divisor, zener, capacitor e
   jumper. Repita os 10 canais (R101…R120, DZ101…110, C101…110, JP101…110).
6. **Analógicas**: R201–R206, JP201, DZ201–DZ204, C201–C204.
7. **Saídas**: Q301–Q303, diodos, resistores e bornes J8/J9/J10.
8. **Conectores** J2/J4/J6/J7/J11 por último (são os mais altos).

> Use soquete para o MCP2515 e para o GPS quando possível; assim você troca o
> módulo sem dessoldar. Zener e diodos têm polaridade — confira a faixa.

## 5. Jumpers e ajustes

| Jumper | Posição | Efeito |
|---|---|---|
| `JP_VUSB` | 1‑2 | Arduino alimentado pelos 5 V da placa (uso normal no carro) |
| `JP_VUSB` | 2‑3 | Arduino alimentado pelo USB (para gravar com a placa sem 12 V) |
| `JP1` | fechado | Liga a terminação de 120 Ω no CAN (barramento curto) |
| `JP101…JP110` | 1‑2 | Entrada espera **sinal 12 V** (divisor 22 k/10 k) |
| `JP101…JP110` | 2‑3 | Entrada espera **chave para GND** (usa pull-up interno) |
| `JP201` | fechado | Ativa pull-up de 1 k no A1 (boia resistiva) |

## 6. Testes antes de instalar

Com o carro desligado e a placa na bancada:

1. **Continuidade**: GND de J2 contínuo com GND do Arduino, GND do MCP2515, GND
   do GPS e emissores de Q301–Q303. Nenhum curto entre +12 V e GND.
2. **Alimentação**: aplique 12 V com fonte limitada a 1 A. Meça ~12 V após o
   fusível e **5,0 V ± 0,2 V** na saída do buck. O LED1 deve acender.
3. **Entradas**: com jumper em 2‑3, cada entrada deve ler `HIGH` em repouso e
   `LOW` quando o borne é ligado ao GND. Com jumper em 1‑2, aplique 12 V e confira
   ~4,7–5,1 V no pino do Arduino.
4. **Analógicas**: aplique 0,5–4,5 V e confira a leitura; no A3 aplique 12 V e
   meça ~3 V no pino (divisor 4:1).
5. **Saídas**: acione D12/D13/D44/D45 pelo firmware de teste e confira o buzzer,
   o LED e o clique dos relés.
6. **CAN/GPS**: com o Mega gravado, confira `candump`/modo demo e o GPS no
   `/dev/ttyS0`/Serial1 a 9600 baud.

Só depois disso instale no carro, sempre com a **bateria desconectada**.

## 7. Segurança elétrica

- Fusível de 3 A é obrigatório e deve ficar **o mais perto possível** do +12 V.
- Use o positivo **após a chave de ignição**; nada deve ficar energizado com o
  carro desligado (exceto, se quiser, o rádio).
- Nunca ligue 12 V direto em pino do Arduino: use sempre os divisores/jumpers
  desta placa.
- Relés: use diodo de roda-livre (já previsto) e não comute cargas indutivas
  grandes pelo próprio borne sem relé/ Fusível adequado.
- Cabos de sinal passam longe de cabos de ignição; use par trançado no CAN.
- O projeto **lê** o OBD‑II; não altere a ECU. Modificações no veículo são de sua
  responsabilidade (ver seção 14 do README principal).

## 8. Limitações conhecidas

- Sem projeto KiCad/Gerber: `board.svg` é desenho mecânico (posições, furos,
  conectores), não trilhas roteadas.
- O netlist é a fonte para conferir a fiação; não substitui o teste com multímetro.
- A pinagem segue `arduino/car_dash/config.h` — se você mudar um pino lá, rode
  `generate.py` novamente para atualizar esquema/BOM/netlist.
