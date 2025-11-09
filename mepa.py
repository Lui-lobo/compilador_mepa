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

from typing import List, Dict, Tuple, Optional
import os
import sys

# -----------------------------
# Helpers e tipos
# -----------------------------
Instruction = Tuple[int, str]  # (linha, instrução_raw)

def clear_console():
    # Não é estritamente necessário, deixar como compatível
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

def pause():
    try:
        input("Pressione Enter para continuar...")
    except KeyboardInterrupt:
        print()

def parse_line_header(s: str) -> Tuple[int, str]:
    """
    Recebe uma string como "120 CRVL 2" e retorna (120, "CRVL 2").
    Lança ValueError se o primeiro token não for inteiro não-negativo.
    """
    s = s.strip()
    if not s:
        raise ValueError("Linha vazia")
    parts = s.split(None, 1)
    if len(parts) == 0:
        raise ValueError("Linha inválida")
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
    Mantém as linhas carregadas em memória, com ordenação por número de linha.
    """
    def __init__(self):
        self.lines: Dict[int, str] = {}  # linha -> conteúdo (instrução raw)
        self.filename: Optional[str] = None
        self.modified: bool = False

    def load_file(self, path: str) -> None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Arquivo '{path}' não encontrado.")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.readlines()
        self.lines.clear()
        for raw in content:
            raw = raw.rstrip('\n').rstrip('\r')
            if not raw.strip():
                continue
            try:
                num, rest = parse_line_header(raw)
            except ValueError:
                # ignora linhas malformatadas do arquivo (ou poderia lançar)
                continue
            self.lines[num] = rest
        self.filename = path
        self.modified = False

    def save_file(self, path: Optional[str] = None) -> None:
        if path is None:
            if self.filename is None:
                raise ValueError("Nenhum arquivo associado para salvar.")
            path = self.filename
        # Escrever ordenado
        with open(path, 'w', encoding='utf-8') as f:
            for num in sorted(self.lines.keys()):
                f.write(f"{num} {self.lines[num]}\n")
        self.filename = path
        self.modified = False

    def list_text(self) -> List[str]:
        out = []
        for num in sorted(self.lines.keys()):
            out.append(f"{num} {self.lines[num]}")
        return out

    def insert(self, num: int, instr: str) -> Tuple[str, Optional[str]]:
        """
        Insere ou substitui. Retorna tupla (mensagem, subtituida_ou_None)
        """
        old = self.lines.get(num)
        if old is None:
            self.lines[num] = instr
            self.modified = True
            return ("Linha inserida", None)
        else:
            self.lines[num] = instr
            self.modified = True
            return ("Linha substituída", old)

    def delete(self, num: int) -> str:
        if num in self.lines:
            removed = self.lines.pop(num)
            self.modified = True
            return removed
        raise KeyError("Linha inexistente")

    def delete_range(self, a: int, b: int) -> List[Tuple[int, str]]:
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
    Interpretador simples da linguagem MEPA.
    Mantém pilha (list), memória (dict de endereços inteiros), instruções e labels.
    """
    def __init__(self, source: SourceBuffer):
        self.src = source
        self.stack: List[int] = []
        self.memory: Dict[int, int] = {}  # endereço -> valor
        self.instructions: List[Tuple[int, List[str]]] = []  # (linha, tokens)
        self.line_to_index: Dict[int, int] = {}  # linha -> índice em instructions
        self.labels: Dict[str, int] = {}  # label -> linha
        self.ip: int = 0  # índice de instrução corrente (0-based)
        self.running: bool = False
        self.halted: bool = False

    # ---------- carregamento ----------
    def prepare(self):
        """
        Constrói a lista de instruções a partir do source buffer,
        extrai labels e prepara map de linha->índice.
        """
        self.instructions.clear()
        self.line_to_index.clear()
        self.labels.clear()
        for i, num in enumerate(sorted(self.src.lines.keys())):
            raw = self.src.lines[num].strip()
            # Ignorar comentários após '#'
            if '#' in raw:
                raw = raw.split('#', 1)[0].strip()
            if not raw:
                continue
            # tratar label no começo do raw como "L1: NADA"
            tokens = raw.split()
            if tokens and tokens[0].endswith(':'):
                label = tokens[0][:-1]
                if label:
                    self.labels[label.upper()] = num
                    tokens = tokens[1:]
            # guarda a instrução como lista de tokens (maiúsculo para opcode)
            tokens = [t for t in tokens]
            self.instructions.append((num, tokens))
        # montar line_to_index
        for idx, (ln, tokens) in enumerate(self.instructions):
            self.line_to_index[ln] = idx

    # ---------- utilitários ----------
    def reset_state(self):
        self.stack = []
        self.memory = {}
        self.ip = 0
        self.running = False
        self.halted = False

    def _lookup_target_index(self, target: str) -> int:
        """
        target pode ser número (string "120") ou label "L2".
        Retorna índice (0-based) em self.instructions.
        Lança KeyError se não encontrar.
        """
        t = target.strip()
        # Se for numérico
        try:
            ln = int(t)
        except Exception:
            ln = None
        if ln is not None:
            if ln in self.line_to_index:
                return self.line_to_index[ln]
            else:
                raise KeyError(f"Linha alvo {ln} inexistente.")
        else:
            # label
            key = t.upper()
            if key in self.labels:
                ln = self.labels[key]
                return self.line_to_index[ln]
            else:
                raise KeyError(f"Label alvo '{t}' inexistente.")

    # ---------- execução ----------
    def run_all(self) -> None:
        """Executa até PARA ou fim das instruções."""
        self.prepare()
        self.reset_state()
        self.running = True
        # Busca INPP obrigatória? Exemplo sugere que INPP seja a primeira instrução normalmente.
        while self.ip < len(self.instructions) and not self.halted:
            self.execute_step()
        self.running = False

    def execute_step(self) -> None:
        """Executa exatamente uma instrução (usada pelo DEBUG/NEXT e pelo run)."""
        if self.halted:
            return
        if self.ip < 0 or self.ip >= len(self.instructions):
            # fim natural: encerra
            self.halted = True
            return
        ln, tokens = self.instructions[self.ip]
        if not tokens:
            # linha vazia / NADA
            self.ip += 1
            return
        op = tokens[0].upper()
        args = tokens[1:]
        # executar instrução
        try:
            # instruções sem operandos
            if op == 'INPP':
                # inicia programa principal -> geralmente reset de estruturas
                # no exemplo, INPP é só indicativo. Aqui não precisa fazer nada específico.
                pass
            elif op == 'PARA':
                self.halted = True
            elif op == 'NADA':
                pass
            elif op == 'IMPR':
                if not self.stack:
                    raise RuntimeError("Pilha vazia em IMPR")
                val = self.stack.pop()
                print(val)
            elif op == 'AMEM':
                if len(args) != 1:
                    raise ValueError("AMEM precisa de 1 argumento")
                m = int(args[0])
                # inicializa endereços 0..m-1 se não existirem
                for i in range(m):
                    if i not in self.memory:
                        self.memory[i] = 0
            elif op == 'DMEM':
                if len(args) != 1:
                    raise ValueError("DMEM precisa de 1 argumento")
                m = int(args[0])
                # desalocar: remove os endereços 0..m-1 se existirem
                for i in range(m):
                    if i in self.memory:
                        del self.memory[i]
            elif op == 'CRCT':
                if len(args) != 1:
                    raise ValueError("CRCT precisa de 1 argumento")
                k = int(args[0])
                self.stack.append(k)
            elif op == 'CRVL':
                if len(args) != 1:
                    raise ValueError("CRVL precisa de 1 argumento")
                n = int(args[0])
                if n not in self.memory:
                    raise KeyError(f"Endereço {n} não alocado")
                self.stack.append(self.memory[n])
            elif op == 'ARMZ':
                if len(args) != 1:
                    raise ValueError("ARMZ precisa de 1 argumento")
                n = int(args[0])
                if not self.stack:
                    raise RuntimeError("Pilha vazia em ARMZ")
                val = self.stack.pop()
                self.memory[n] = val
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
            elif op == 'INVR':
                if not self.stack:
                    raise RuntimeError("Pilha vazia em INVR")
                v = self.stack.pop()
                self.stack.append(-v)
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
            elif op in ('CMME', 'CMMA', 'CMIG', 'CMDG', 'CMEG', 'CMAG'):
                if len(self.stack) < 2:
                    raise RuntimeError(f"Pilha com menos de 2 elementos em {op}")
                b = self.stack.pop()
                a = self.stack.pop()
                res = 0
                if op == 'CMME':
                    res = 1 if (a < b) else 0
                elif op == 'CMMA':
                    res = 1 if (a > b) else 0
                elif op == 'CMIG':
                    res = 1 if (a == b) else 0
                elif op == 'CMDG':
                    res = 1 if (a != b) else 0
                elif op == 'CMEG':
                    res = 1 if (a <= b) else 0
                elif op == 'CMAG':
                    res = 1 if (a >= b) else 0
                self.stack.append(res)
            elif op == 'DSVS':
                if len(args) != 1:
                    raise ValueError("DSVS precisa de 1 argumento (endereço ou label)")
                target = args[0]
                idx = self._lookup_target_index(target)
                self.ip = idx
                return  # já atualizamos ip
            elif op == 'DSVF':
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
            # melhor tornar o erro legível e interromper execução
            raise RuntimeError(f"Erro ao executar linha {ln}: {e}") from e
        # se não fizemos jump, avançar ip normalmente
        self.ip += 1

    # ---------- modo debug ----------
    def start_debug(self):
        self.prepare()
        self.reset_state()
        self.running = True
        # No debug, não executa nada até NEXT
        print("Iniciando modo de depuração:")
        self._print_current_instruction()

    def _print_current_instruction(self):
        if 0 <= self.ip < len(self.instructions):
            ln, tokens = self.instructions[self.ip]
            instr_text = " ".join(tokens) if tokens else "<vazio>"
            print(f"{ln} {instr_text}")
        else:
            print("<fim do programa>")

    def debug_next(self):
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
        if not self.stack:
            print("Conteúdo da pilha: (vazia)")
            return
        print("Conteúdo da pilha:")
        for i, v in enumerate(self.stack):
            print(f"{i}: {v}")

# -----------------------------
# REPL e comando handlers
# -----------------------------
def cmd_load(state: SourceBuffer, arg: str):
    path = arg.strip()
    if not path:
        print("Uso: LOAD <ARQUIVO.MEPA>")
        return
    # confirmar se há modificações não salvas
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
            a = int(parts[0]); b = int(parts[1])
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
    if not state.lines:
        print("Nenhum código carregado na memória.")
        return
    interp = MepaInterpreter(state)
    interp.start_debug()
    # modo interativo do depurador
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
        elif cmd in ('LOAD', 'RUN', 'INS', 'DEL', 'EXIT', 'SAVE'):
            # comandos que interrompem depuração segundo enunciado
            print(f"Comando '{cmd}' interrompe o modo de depuração.")
            # devolve controle indicando interrupção
            break
        else:
            print("Comando inválido no modo DEBUG. Use NEXT, STACK ou STOP.")

# -----------------------------
# Loop principal
# -----------------------------
def main():
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

if __name__ == '__main__':
    main()
