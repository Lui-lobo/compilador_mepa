# 🧮 Interpretador da Linguagem MEPA Simplificada

Trabalho da disciplina **Compiladores** – Implementação de um **interpretador da linguagem MEPA** (versão simplificada) em Python.

O projeto implementa um ambiente interativo (REPL – *Read-Eval-Print-Loop*) capaz de:
- Ler, editar e executar programas escritos na linguagem MEPA simplificada;
- Manipular memória e pilha de execução;
- Executar programas passo a passo (modo DEBUG);
- Salvar e carregar arquivos `.mepa`.

---

## 🧠 Sobre o Projeto

A linguagem **MEPA (Máquina de Execução Para Algoritmos)** foi proposta por Tomasz Kowaltowski no livro *Implementação de Linguagens de Programação* (1983).  
Este interpretador tem o objetivo de simular o funcionamento básico da MEPA, executando instruções linha a linha, com suporte a labels, operações aritméticas, lógicas e comparações.

O sistema é composto por um **REPL interativo** que reconhece comandos e um **interpretador interno** responsável por processar e executar o código carregado.

---

## 🏗️ Estrutura de Arquivos

```bash
MEPA/
├── MEPA.py # Programa principal (REPL + interpretador)
├── tests/
│ ├── ex01.mepa # Programa correto (fatorial)
│ ├── ex02.mepa # Programa com erros
│ └── ex03.mepa # Testes de comparação/lógica
└── README.md # Este arquivo
```


---

## 🚀 Como Executar

Requisitos:
- Python **3.8+**
- Sistema operacional Windows, Linux ou macOS
- Terminal interativo

Para iniciar o interpretador:

```bash
python MEPA.py
```

O sistema exibirá o prompt:

```bash
MEPA Interpreter - REPL
Digite um comando. Ex.: LOAD arquivo.mepa | LIST | RUN | INS | DEL | SAVE | DEBUG | EXIT
>
```

# 🧩 Comandos Disponíveis

LOAD
Sintaxe: LOAD <CAMINHO>
Descrição: Carrega um arquivo .mepa na memória.
Observações: Se houver alterações não salvas, o programa pergunta se deseja salvar antes.

LIST
Sintaxe: LIST
Descrição: Exibe o código MEPA carregado, 20 linhas por página.
Observações: Mostra o número da linha e a instrução correspondente.

INS
Sintaxe: INS <LINHA> <INSTRUÇÃO>
Descrição: Insere ou substitui uma linha no código.
Exemplo: INS 250 CRCT 7
Observações: Se a linha já existir, ela é substituída.

DEL
Sintaxe:
DEL <LINHA>
DEL <LINHA_INICIAL> <LINHA_FINAL>
Descrição: Remove uma linha específica ou um intervalo de linhas.
Observações: Exibe as linhas removidas.

SAVE
Sintaxe: SAVE
Descrição: Salva o código atual em disco.
Observações: Se o arquivo ainda não tiver nome, o sistema solicita um.

RUN
Sintaxe: RUN
Descrição: Executa o programa inteiro até encontrar a instrução PARA.
Observações: Exibe os valores impressos por instruções IMPR.

DEBUG
Sintaxe: DEBUG
Descrição: Inicia o modo de depuração, permitindo execução passo a passo.
Comandos disponíveis dentro do DEBUG:
NEXT → Executa a próxima instrução MEPA.
STACK → Mostra o conteúdo da pilha.
STOP → Sai do modo de depuração.

Observações: Qualquer comando como LOAD, RUN, INS, DEL, EXIT ou SAVE interrompe o modo DEBUG.

EXIT
Sintaxe: EXIT
Descrição: Encerra o programa.
Observações: Caso existam alterações não salvas, o programa solicita confirmação antes de sair.

# 🧪 Exemplo de Uso
## 1. Carregar e executar o programa de fatorial
```bash
> LOAD tests/ex01.mepa
Arquivo 'tests/ex01.mepa' carregado com sucesso.
> RUN
120
Execução finalizada.
```

## 2. Inserir novas instruções
```bash
> INS 270 CRCT 999
Linha inserida:
270 CRCT 999
> INS 271 IMPR
Linha inserida:
271 IMPR
> INS 272 PARA
Linha inserida:
272 PARA
> RUN
120
999
Execução finalizada.
```

## 3. Depurar o código passo a passo
```bash
> DEBUG
Iniciando modo de depuração:
10 INPP
> NEXT
20 AMEM 3
> NEXT
30 CRCT 5
> STACK
Conteúdo da pilha:
0: 5
> STOP
Modo de depuração finalizado!
```

# 🧮 Instruções Suportadas da Linguagem MEPA
## As instruções disponíveis nesta versão simplificada são:
INPP → Inicia o programa principal
AMEM m → Aloca m posições de memória
DMEM m → Desaloca m posições de memória
PARA → Interrompe a execução do programa
CRCT k → Carrega uma constante k no topo da pilha
CRVL n → Carrega o valor da memória n no topo da pilha
ARMZ n → Armazena o valor do topo da pilha na posição n
SOMA, SUBT, MULT, DIVI → Operações aritméticas
INVR → Inverte o sinal do topo da pilha
CONJ, DISJ → E lógico / OU lógico
CMME, CMMA, CMIG, CMDG, CMEG, CMAG → Comparações entre dois valores
DSVS p → Desvio incondicional para o endereço ou label p
DSVF p → Desvio se falso (0) para o endereço ou label p
NADA → Instrução nula (sem efeito)
IMPR → Imprime o valor do topo da pilha
Observações:
Comentários são iniciados por #.
Labels podem ser definidos como L1: e referenciados em desvios (DSVS L1, DSVF L2).

# 🧱 Estrutura Interna do Sistema
Classe SourceBuffer → Gerencia o código-fonte na memória (carregar, inserir, deletar, salvar).
Classe MepaInterpreter → Executa as instruções MEPA, controlando pilha, memória e saltos.
Funções REPL → Interpretam comandos do usuário (LOAD, LIST, RUN, etc.).
Modo DEBUG → Permite executar passo a passo e visualizar o estado da pilha.
Memória e pilha → Implementadas em Python usando dict e list.