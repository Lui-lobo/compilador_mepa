#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEPA.py - Interpretador simplificado da linguagem MEPA com REPL

Grupo: 
Luiz Henrique Carvalhas Lobo de Oliveira - RA: 2301293 - CC06
Johnathan Silva Francisco - RA: 2301490 - CC06
Enzo Tavares Lula Silva - RA: 2301843 - CC06
Abner Israel Sanches de Oliveira - RA: 2300152 - CC06
Lucas Araújo Andrade Morais - RA: 2300734 - CC06

Documento: Trabalho 03 - Interpretador MEPA
Linguagem: Python 3.x
"""

# Importações necessárias
from typing import List, Dict, Tuple, Optional
import os
import sys

# -----------------------------
# Helpers e tipos
# -----------------------------
Instruction = Tuple[int, str]  # Define um tipo para uma instrução (linha, conteúdo)

def clear_console():
    """
    Limpa o console conforme o sistema operacional.
    Não é necessário ao funcionamento, mas deixado para compatibilidade.
    """
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def pause():
    """
    Pausa a execução até que o usuário pressione Enter.
    Usado quando o LIST mostra páginas de 20 linhas.
    """
    try:
        input("Pressione Enter para continuar...")
    except KeyboardInterrupt:
        print()

def parse_line_header(s: str) -> Tuple[int, str]:
    """
    Recebe uma linha do arquivo, por ex.: "120 CRVL 2"
    Separa o número da linha do restante do conteúdo.
    Retorna (120, "CRVL 2").
    """
    s = s.strip()
    if not s:
        raise ValueError("Linha vazia")

    parts = s.split(None, 1)  # divide apenas em dois tokens: número e resto

    if len(parts) == 0:
        raise ValueError("Linha inválida")

    # Primeiro token deve ser um número
    try:
        numero = int(parts[0])
    except Exception:
        raise ValueError("Número de linha inválido")

    if numero < 0:
        raise ValueError("Número de linha não pode ser negativo")

    rest = parts[1] if len(parts) > 1 else ""
    return numero, rest.strip()

# -----------------------------
# Estrutura de armazenamento do código (em memória)
# -----------------------------
class SourceBuffer:
    """
    Classe responsável por armazenar o código MEPA carregado.
    Permite inserir, deletar, listar e salvar linhas numeradas.
    """

    def __init__(self):
        # Dicionário: número_da_linha -> instrução_raw
        self.lines: Dict[int, str] = {}
        self.filename: Optional[str] = None
        self.modified: bool = False  # indica se houve alterações após o load

    def load_file(self, path: str) -> None:
        """
        Carrega um arquivo .mepa para a memória.
        Faz parsing de cada linha usando parse_line_header().
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Arquivo '{path}' não encontrado.")

        # Lê todas as linhas do arquivo
        with open(path, 'r', encoding='utf-8') as f:
            content = f.readlines()

        self.lines.clear()

        # Processa linha por linha
        for raw in content:
            raw = raw.rstrip('\n').rstrip('\r')
            if not raw.strip():
                continue  # ignora linhas vazias
            try:
                num, rest = parse_line_header(raw)
            except ValueError:
                continue  # ignora linhas mal formatadas
            self.lines[num] = rest

        self.filename = path
        self.modified = False

    def save_file(self, path: Optional[str] = None) -> None:
        """
        Salva o conteúdo atual em um arquivo, ordenando as linhas.
        """
        if path is None:
            if self.filename is None:
                raise ValueError("Nenhum arquivo associado para salvar.")
            path = self.filename

        with open(path, 'w', encoding='utf-8') as f:
            for num in sorted(self.lines.keys()):
                f.write(f"{num} {self.lines[num]}\n")

        self.filename = path
        self.modified = False

    def list_text(self) -> List[str]:
        """
        Retorna uma lista de strings: ["10 INPP", "20 AMEM 3", ...]
        Usado pelo comando LIST.
        """
        out = []
        for num in sorted(self.lines.keys()):
            out.append(f"{num} {self.lines[num]}")
        return out

    def insert(self, num: int, instr: str) -> Tuple[str, Optional[str]]:
        """
        Insere ou substitui uma linha.

        Retorna:
        - "Linha inserida" se nova
        - "Linha substituída" e o conteúdo antigo, se já existia
        """
        old = self.lines.get(num)
        if old is None:  # nova linha
            self.lines[num] = instr
            self.modified = True
            return ("Linha inserida", None)
        else:  # substituição
            self.lines[num] = instr
            self.modified = True
            return ("Linha substituída", old)

    def delete(self, num: int) -> str:
        """
        Remove uma linha específica.
        """
        if num in self.lines:
            removed = self.lines.pop(num)
            self.modified = True
            return removed
        raise KeyError("Linha inexistente")

    def delete_range(self, a: int, b: int) -> List[Tuple[int, str]]:
        """
        Remove várias linhas no intervalo [a, b].
        """
        if a > b:
            raise ValueError("Intervalo inválido")

        removed = []

        for num in sorted(list(self.lines.keys())):
            if a <= num <= b:
                removed.append((num, self.lines.pop(num)))

        if removed:
            self.modified = True

        return removed

# -----------------------------
# Interpretador MEPA
# -----------------------------
class MepaInterpreter:
    """
    Classe central: executa instruções MEPA.
    Mantém:
    - pilha
    - memória
    - lista de instruções
    - labels
    - ponteiro de instrução (ip)
    """

    def __init__(self, source: SourceBuffer):
        self.src = source
        self.stack: List[int] = []     # pilha de execução
        self.memory: Dict[int, int] = {}  # memória endereçada
        self.instructions: List[Tuple[int, List[str]]] = []  # lista de (linha, tokens)
        self.line_to_index: Dict[int, int] = {}  # mapeia número da linha -> índice
        self.labels: Dict[str, int] = {}  # mapeia nome do label -> linha
        self.ip: int = 0        # instruction pointer (indice da lista instructions)
        self.running: bool = False
        self.halted: bool = False

    # ---------- carregamento ----------
    def prepare(self):
        """
        Constrói lista padronizada de instruções.
        Remove comentários, extrai labels e monta o mapping linha->índice.
        """
        self.instructions.clear()
        self.line_to_index.clear()
        self.labels.clear()

        # Processa cada linha na ordem crescente
        for i, num in enumerate(sorted(self.src.lines.keys())):
            raw = self.src.lines[num].strip()

            # Remove comentários iniciados por '#'
            if '#' in raw:
                raw = raw.split('#', 1)[0].strip()

            if not raw:
                continue  # ignora linha vazia

            tokens = raw.split()

            # Se o primeiro token termina com ':', é um label
            if tokens and tokens[0].endswith(':'):
                label = tokens[0][:-1]
                if label:
                    self.labels[label.upper()] = num  # registra label → linha
                    tokens = tokens[1:]  # remove o label para obter instrução real

            # Armazena a instrução (linha, lista_tokens)
            tokens = [t for t in tokens]  # copia
            self.instructions.append((num, tokens))

        # Monta o mapeamento linha -> índice da lista instructions
        for idx, (ln, tokens) in enumerate(self.instructions):
            self.line_to_index[ln] = idx

    # ---------- utilitários ----------
    def reset_state(self):
        """
        Limpa pilha, memória e posição de execução.
        """
        self.stack = []
        self.memory = {}
        self.ip = 0
        self.running = False
        self.halted = False

    def _lookup_target_index(self, target: str) -> int:
        """
        Resolve destino de saltos (DSVS, DSVF).
        target pode ser:
        - um número de linha ("120")
        - um label ("L1")

        Retorna índice na lista self.instructions.
        """
        t = target.strip()

        # Se for número
        try:
            ln = int(t)
        except Exception:
            ln = None

        if ln is not None:
            if ln in self.line_to_index:
                return self.line_to_index[ln]
            raise KeyError(f"Linha alvo {ln} inexistente.")

        # Se for label
        key = t.upper()
        if key in self.labels:
            ln = self.labels[key]
            return self.line_to_index[ln]

        raise KeyError(f"Label alvo '{t}' inexistente.")

    # ---------- execução ----------
    def run_all(self) -> None:
        """
        Executa programa inteiro até encontrar PARA ou acabar instruções.
        """
        self.prepare()      # constrói instruções
        self.reset_state()  # zera pilha e memória
        self.running = True

        while self.ip < len(self.instructions) and not self.halted:
            self.execute_step()

        self.running = False

    def execute_step(self) -> None:
        """
        Executa UMA instrução (para NEXT ou execução normal do run_all).
        """

        if self.halted:
            return

        # Se ip saiu dos limites, encerrou naturalmente
        if self.ip < 0 or self.ip >= len(self.instructions):
            self.halted = True
            return

        # Obtém (número_da_linha, tokens)
        ln, tokens = self.instructions[self.ip]

        if not tokens:
            # linha vazia equivale a NADA
            self.ip += 1
            return

        op = tokens[0].upper()  # operação
        args = tokens[1:]       # argumentos

        # Bloco gigante com todas instruções MEPA
        try:
            # ------- INSTRUÇÕES SEM ARGUMENTO -------
            if op == 'INPP':
                pass  # apenas marca início, não faz ação interna

            elif op == 'PARA':
                # Finaliza execução
                self.halted = True

            elif op == 'NADA':
                pass

            elif op == 'IMPR':
                if not self.stack:
                    raise RuntimeError("Pilha vazia em IMPR")
                val = self.stack.pop()
                print(val)

            # ------- MEMÓRIA -------
            elif op == 'AMEM':
                # Aloca m posições de memória e inicializa com zero
                if len(args) != 1:
                    raise ValueError("AMEM precisa de 1 argumento")
                m = int(args[0])
                for i in range(m):
                    if i not in self.memory:
                        self.memory[i] = 0

            elif op == 'DMEM':
                # Remove m posições da memória
                if len(args) != 1:
                    raise ValueError("DMEM precisa de 1 argumento")
                m = int(args[0])
                for i in range(m):
                    if i in self.memory:
                        del self.memory[i]

            # ------- CRVL / ARMZ / CRCT -------
            elif op == 'CRCT':
                # Empilha um inteiro constante
                if len(args) != 1:
                    raise ValueError("CRCT precisa de 1 argumento")
                k = int(args[0])
                self.stack.append(k)

            elif op == 'CRVL':
                # Carrega valor da memória e empilha
                if len(args) != 1:
                    raise ValueError("CRVL precisa de 1 argumento")
                n = int(args[0])
                if n not in self.memory:
                    raise KeyError(f"Endereço {n} não alocado")
                self.stack.append(self.memory[n])

            elif op == 'ARMZ':
                # Armazena topo da pilha em memória[n]
                if len(args) != 1:
                    raise ValueError("ARMZ precisa de 1 argumento")
                n = int(args[0])
                if not self.stack:
                    raise RuntimeError("Pilha vazia em ARMZ")
                val = self.stack.pop()
                self.memory[n] = val

            # ------- ARITMÉTICAS -------
            elif op in ('SOMA', 'SUBT', 'MULT', 'DIVI'):
                if len(self.stack) < 2:
                    raise RuntimeError(f"Pilha com menos de 2 elementos em {op}")
                b = self.stack.pop()
                a = self.stack.pop()

                if op == 'SOMA':
                    self.stack.append(a + b)
                elif op == 'SUBT':
                    self.stack.append(a - b)
                elif op == 'MULT':
                    self.stack.append(a * b)
                elif op == 'DIVI':
                    if b == 0:
                        raise ZeroDivisionError("Divisão por zero em DIVI")
                    self.stack.append(a // b)

            # ------- UNÁRIA -------
            elif op == 'INVR':
                if not self.stack:
                    raise RuntimeError("Pilha vazia em INVR")
                v = self.stack.pop()
                self.stack.append(-v)

            # ------- LÓGICAS -------
            elif op == 'CONJ':
                if len(self.stack) < 2:
                    raise RuntimeError("Pilha com menos de 2 elementos em CONJ")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if (a and b) else 0)

            elif op == 'DISJ':
                if len(self.stack) < 2:
                    raise RuntimeError("Pilha com menos de 2 elementos em DISJ")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if (a or b) else 0)

            # ------- COMPARAÇÕES -------
            elif op in ('CMME', 'CMMA', 'CMIG', 'CMDG', 'CMEG', 'CMAG'):
                if len(self.stack) < 2:
                    raise RuntimeError(f"Pilha com menos de 2 elementos em {op}")
                b = self.stack.pop()
                a = self.stack.pop()

                res = 0
                if op == 'CMME': res = 1 if a < b else 0
                elif op == 'CMMA': res = 1 if a > b else 0
                elif op == 'CMIG': res = 1 if a == b else 0
                elif op == 'CMDG': res = 1 if a != b else 0
                elif op == 'CMEG': res = 1 if a <= b else 0
                elif op == 'CMAG': res = 1 if a >= b else 0

                self.stack.append(res)

            # ------- DESVIOS -------
            elif op == 'DSVS':
                # Desvio incondicional
                if len(args) != 1:
                    raise ValueError("DSVS precisa de 1 argumento (endereço ou label)")
                target = args[0]
                idx = self._lookup_target_index(target)
                self.ip = idx
                return  # importante: evita ip += 1

            elif op == 'DSVF':
                # Desvio condicional: só desvia se topo == 0
                if len(args) != 1:
                    raise ValueError("DSVF precisa de 1 argumento (endereço ou label)")
                if not self.stack:
                    raise RuntimeError("Pilha vazia em DSVF")
                cond = self.stack.pop()
                if cond == 0:
                    target = args[0]
                    idx = self._lookup_target_index(target)
                    self.ip = idx
                    return

            else:
                raise ValueError(f"Instrução desconhecida '{op}' na linha {ln}")

        except Exception as e:
            # Erros são encapsulados com o número da linha como contexto
            raise RuntimeError(f"Erro ao executar linha {ln}: {e}") from e

        # Se não houve salto, avança para próxima instrução
        self.ip += 1

    # ---------- modo debug ----------
    def start_debug(self):
        """
        Inicia depuração:
        - Prepara instruções
        - Reseta estado
        - Exibe a primeira instrução
        """
        self.prepare()
        self.reset_state()
        self.running = True

        print("Iniciando modo de depuração:")
        self._print_current_instruction()

    def _print_current_instruction(self):
        """
        Imprime a instrução atual baseada em self.ip.
        """
        if 0 <= self.ip < len(self.instructions):
            ln, tokens = self.instructions[self.ip]
            instr_text = " ".join(tokens) if tokens else "<vazio>"
            print(f"{ln} {instr_text}")
        else:
            print("<fim do programa>")

    def debug_next(self):
        """
        Executa a próxima instrução no modo DEBUG.
        """
        if self.halted:
            print("Programa já finalizado.")
            return

        try:
            self._print_current_instruction()
            self.execute_step()
            if self.halted:
                print("Programa finalizado (PARA ou fim).")
        except Exception as e:
            print(f"Erro durante NEXT: {e}")
            self.halted = True

    def debug_stack(self):
        """
        Mostra o conteúdo atual da pilha.
        """
        if not self.stack:
            print("Conteúdo da pilha: (vazia)")
            return
        print("Conteúdo da pilha:")
        for i, v in enumerate(self.stack):
            print(f"{i}: {v}")

# -----------------------------
# REPL e comandos
# -----------------------------
def cmd_load(state: SourceBuffer, arg: str):
    """
    Implementação do comando LOAD.
    Pode solicitar salvamento se houver alterações não gravadas.
    """
    path = arg.strip()
    if not path:
        print("Uso: LOAD <ARQUIVO.MEPA>")
        return

    # Confirma salvar se houver modificações pendentes
    if state.filename and state.modified:
        resp = input(f"Arquivo atual ('{state.filename}') contém alterações não salvas.\nDeseja salvar (S/N)? ").strip().upper()
        if resp == 'S':
            try:
                state.save_file()
                print(f"Arquivo '{state.filename}' salvo com sucesso.")
            except Exception as e:
                print(f"Erro ao salvar: {e}")
                return

    try:
        state.load_file(path)
        print(f"Arquivo '{path}' carregado com sucesso.")
    except Exception as e:
        print(f"Erro ao carregar o arquivo: {e}")

def cmd_list(state: SourceBuffer):
    """
    Lista o código em páginas de 20 linhas.
    """
    lines = state.list_text()
    if not lines:
        print("Nenhum código carregado.")
        return

    page_size = 20
    for i in range(0, len(lines), page_size):
        for line in lines[i:i+page_size]:
            print(line)
        if i + page_size < len(lines):
            pause()

def cmd_ins(state: SourceBuffer, rest: str):
    """
    Insere ou substitui linhas.
    Sintaxe: INS <linha> <instrução>
    """
    rest = rest.strip()
    if not rest:
        print("Uso: INS <LINHA> <INSTRUÇÃO>")
        return

    parts = rest.split(None, 1)
    if len(parts) == 0:
        print("Parâmetros inválidos.")
        return

    try:
        linha = int(parts[0])
    except Exception:
        print("Número de linha inválido.")
        return

    instr = parts[1] if len(parts) > 1 else ""

    msg, old = state.insert(linha, instr)

    if old is None:
        print("Linha inserida:")
        print(f"{linha} {instr}")
    else:
        print("Linha substituída:")
        print("De")
        print(f"{linha} {old}")
        print("Para")
        print(f"{linha} {instr}")

def cmd_del(state: SourceBuffer, rest: str):
    """
    Apaga uma linha ou um intervalo de linhas.
    """
    rest = rest.strip()
    if not rest:
        print("Uso: DEL <LINHA>  ou DEL <LINHA_INI> <LINHA_FIM>")
        return

    parts = rest.split()

    try:
        if len(parts) == 1:
            ln = int(parts[0])
            removed = state.delete(ln)
            print("Linha removida:")
            print(f"{ln} {removed}")

        elif len(parts) == 2:
            a = int(parts[0])
            b = int(parts[1])
            removed = state.delete_range(a, b)

            if not removed:
                print("Nenhuma linha no intervalo.")
            else:
                print("Linhas removidas:")
                for ln, instr in removed:
                    print(f"{ln} {instr}")
        else:
            print("Parâmetros inválidos para DEL")

    except ValueError as ve:
        print(f"Erro: {ve}")

    except KeyError as ke:
        print(f"Erro: {ke}")

def cmd_save(state: SourceBuffer):
    """
    Salva o arquivo atual ou pede nome novo.
    """
    try:
        if state.filename is None:
            path = input("Nome do arquivo para salvar: ").strip()
            if not path:
                print("Operação cancelada.")
                return
            state.save_file(path)
            print(f"Arquivo '{path}' salvo com sucesso.")
        else:
            state.save_file()
            print(f"Arquivo '{state.filename}' salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao salvar arquivo: {e}")

def cmd_run(state: SourceBuffer):
    """
    Executa o programa completo.
    """
    if not state.lines:
        print("Nenhum código carregado na memória.")
        return

    interp = MepaInterpreter(state)

    try:
        interp.run_all()
        print("Execução finalizada.")
    except Exception as e:
        print(f"Erro durante execução: {e}")

def cmd_debug(state: SourceBuffer):
    """
    Inicia o modo de depuração interativa.
    """
    if not state.lines:
        print("Nenhum código carregado na memória.")
        return

    interp = MepaInterpreter(state)
    interp.start_debug()

    # Loop de comandos do DEBUG
    while True:
        try:
            cmd = input("> ").strip().upper()
        except KeyboardInterrupt:
            print("\nDepuração interrompida.")
            break

        if cmd == "":
            continue

        if cmd == 'NEXT':
            interp.debug_next()
            if interp.halted:
                break

        elif cmd == 'STACK':
            interp.debug_stack()

        elif cmd == 'STOP':
            print("Modo de depuração finalizado!")
            break

        # comandos que fecham debug
        elif cmd in ('LOAD', 'RUN', 'INS', 'DEL', 'EXIT', 'SAVE'):
            print(f"Comando '{cmd}' interrompe o modo de depuração.")
            break

        else:
            print("Comando inválido no modo DEBUG. Use NEXT, STACK ou STOP.")

# -----------------------------
# Loop principal do REPL
# -----------------------------
def main():
    """
    Loop principal do REPL.
    Aguarda comandos do usuário e os encaminha ao handler correto.
    """
    state = SourceBuffer()

    print("MEPA Interpreter - REPL")
    print("Digite um comando. Ex.: LOAD arquivo.mepa | LIST | RUN | INS | DEL | SAVE | DEBUG | EXIT")

    while True:
        try:
            raw = input("> ")
        except EOFError:
            print("\nSaindo...")
            break
        except KeyboardInterrupt:
            print("\nUse EXIT para encerrar.")
            continue

        if not raw:
            continue

        parts = raw.strip().split(None, 1)

        cmd = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ""

        # Encaminha para o comando correspondente
        if cmd == 'LOAD':
            cmd_load(state, arg)
        elif cmd == 'LIST':
            cmd_list(state)
        elif cmd == 'INS':
            cmd_ins(state, arg)
        elif cmd == 'DEL':
            cmd_del(state, arg)
        elif cmd == 'SAVE':
            cmd_save(state)
        elif cmd == 'RUN':
            cmd_run(state)
        elif cmd == 'DEBUG':
            cmd_debug(state)
        elif cmd == 'EXIT':
            # Verifica se há alterações não salvas
            if state.modified and state.filename:
                resp = input(f"Arquivo atual ('{state.filename}') contém alterações não salvas.\nDeseja salvar (S/N)? ").strip().upper()
                if resp == 'S':
                    try:
                        state.save_file()
                        print(f"Arquivo '{state.filename}' salvo com sucesso.")
                    except Exception as e:
                        print(f"Erro ao salvar: {e}")
                        continue

            elif state.modified and state.filename is None:
                resp = input("Existem alterações não salvas. Deseja salvar (S/N)? ").strip().upper()
                if resp == 'S':
                    path = input("Nome do arquivo para salvar: ").strip()
                    if path:
                        try:
                            state.save_file(path)
                            print(f"Arquivo '{path}' salvo com sucesso.")
                        except Exception as e:
                            print(f"Erro ao salvar: {e}")
                            continue

            print("Fim da execução.")
            break

        else:
            print("Erro: comando inválido")

# Ponto de entrada
if __name__ == '__main__':
    main()
