"""O `iniciar <trilha>` de um projeto pelo plugin e a conferência do repositório de código (spec do porte 1, §7.5 e
§7.6; spec 6d-repositorio, §7).

O `iniciar` copia o modelo da trilha, `modelo/<trilha>/` na raiz do plugin, e o lançador, `modelo/lancador.py`, troca
as marcas, mescla o do modelo no `.claude/settings.json` que a pasta já tem, liga os githooks e instala os plugins da
trilha pelo `claude`; no planejamento, roda o `gerar`. O núcleo, as skills, os agentes, o workflow e o mod vêm do plugin
e não são copiados. O `conferir` diz o que falta no repositório de código para o primeiro bloco."""
from __future__ import annotations

import copy
import datetime
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Mapping

import bloco
import ci
import comum
import gerador
import invariantes
import linear
import perfil_comum
import perfil_desenvolvimento

ORIGEM = comum.raiz_do_nucleo()
AJUDA = """\
Inicia um projeto pelo plugin, nas duas trilhas (spec do porte 1, §7.5), ou confere o repositório de código (spec
6d-repositorio, §7.4).

- `harness.py iniciar <trilha> [<pasta>] [--nome <nome>]`: a `<trilha>` é `planejamento` ou `desenvolvimento`, e a
  `<pasta>`, a raiz de um repositório git sem o harness; sem ela, a pasta atual. Copia, sem sobrescrever nada, o modelo
  da trilha (`modelo/<trilha>/` do plugin) e o lançador, `.claude/harness/harness.py`, executável. Em todo arquivo de
  texto copiado, troca `{{PROJETO}}` pelo `--nome` ou, sem ele, pelo nome da pasta, e `{{DATA}}` pela data
  de hoje. O que já existe fica como está, com uma linha `mantido: <caminho>`; a do `CLAUDE.md` mantido diz as linhas
  `@` do modelo que faltam nele. O `.gitignore` da equipe recebe só as linhas do modelo que faltam. O
  `.claude/settings.json` que a pasta já tem, como o que a instalação do plugin grava, recebe do modelo o que falta: em cada lista do `permissions`, as regras que faltam, no fim e na ordem
  do modelo; as outras chaves, como o `extraKnownMarketplaces.<nome>` e o `enabledPlugins.<id>`, só se faltarem, e a
  `ref` instalada fica. Com algo acrescentado, a linha é `mesclado: .claude/settings.json`; sem nada, `mantido:`. Liga o
  `core.hooksPath` aos githooks e instala os plugins da trilha pelo `claude plugin`, com o `--scope project`: o
  `ela-harness` e, no desenvolvimento, o `ela-harness-papeis`. O `.github/workflows/harness.yml` não vem do modelo:
  o `iniciar` o escreve, nas duas trilhas, igual ao do `gerar`, com o ramo do perfil (`main` no planejamento), lido
  sem validar o perfil, e a `ref` do settings já mesclado. O arquivo que já existe fica, com `mantido:`. A `ref`
  que não é a tag da versão do plugin carregado, ou o settings sem `ref`, dá a linha da recusa e nenhum arquivo, sem recusar o `iniciar`. O
  núcleo, as skills, os agentes e o workflow vêm do plugin e não são copiados.
- Com o `git config` falhando, sem o `claude` ou com ele falhando, a cópia fica, a linha do `core.hooksPath` ou a dos
  `plugins` diz o que falta e o código de saída é 0. O arquivo que não se grava ou não se lê, e o fora do UTF-8, saem
  com 1 e a linha `erro: <motivo>`.
- Recusa, antes de gravar qualquer coisa: sem o modelo ou o lançador no plugin, a `<pasta>` que não é a raiz de um
  repositório git, a `<pasta>` que já tem o lançador e o `.claude/settings.json` existente que não é um objeto JSON:
  `.claude/settings.json: JSON malformado na linha <n>; corrija o arquivo e rode o iniciar de novo` ou
  `.claude/settings.json: não é um objeto JSON; corrija o arquivo e rode o iniciar de novo`.
- `harness.py iniciar --conferir`: roda dentro do repositório de código e diz o que ainda falta para o primeiro
  bloco, um item por linha, na ordem: `perfil`, `plugin`, `githooks`, `.gitignore`, `ci`, `passagem`, `invariantes`,
  `instalado` e, só com a `[desenvolvimento.linear]` no perfil válido, `linear` (o item 9). O item `plugin` confere, no
  `.claude/settings.json`, o `extraKnownMarketplaces.ela-harness` do GitHub `Ela-Decora/ela-harness`, com `ref`, e os
  dois plugins no `enabledPlugins`, e depois o lançador. O item `instalado` confere os dois plugins habilitados para a
  pasta ou para o usuário, pelo `claude plugin list --json`, com o tempo limite de 30 s: a instalação vale por pasta,
  e cada clone novo roda os comandos uma vez. O item `.gitignore` confere as linhas fixas e, com o perfil válido, os
  arquivos da lane que o `lane abrir` confere (o `.env` do `env_modelo` e os `env_copiados`), pelo `git check-ignore`.
  O item `ci` compara o `.github/workflows/harness.yml` com o gerado, pelo ramo do perfil, lido sem validá-lo, e pela
  `ref` do settings; ausente ou diferente, ou com a recusa de versão ou a do settings, diz `ci: falta`.
  O item `linear` confere a chave `LINEAR_API_KEY` do ambiente e lê do Linear o time, o projeto e os rótulos do perfil,
  numa chamada só, de no máximo 10 s: diz `linear: ok` ou o que falta, e nunca mostra a chave. Cada linha é
  `<item>: ok` ou `<item>: falta: <o quê>; <comando>`, e um item que falha não impede os seguintes. Sai com 1 se
  alguma linha tem `falta`.
- O ramo principal e a pasta do backlog vêm do `.claude/perfil.toml` que a `<pasta>` já tiver; sem ele, `main` e
  `docs/backlog`.
"""
PLANEJAMENTO = perfil_comum.PLANEJAMENTO
DESENVOLVIMENTO = perfil_comum.DESENVOLVIMENTO
TRILHAS = (PLANEJAMENTO, DESENVOLVIMENTO)
PLUGINS: dict[str, tuple[str, ...]] = {
    PLANEJAMENTO: ("ela-harness@ela-harness",),
    DESENVOLVIMENTO: ("ela-harness@ela-harness", "ela-harness-papeis@ela-harness"),
}
# As três constantes que a sonda decidiu (decisão 1 do plano, Task 1 do porte 1). O `--scope project` grava só o
# `enabledPlugins` e o `extraKnownMarketplaces`; a ferramenta Workflow acha o workflow do plugin; o `ela-harness-papeis`
# carrega como segundo plugin do mesmo marketplace. Com o `MOD_PELO_MARKETPLACE_DE_PASTA` falso, sai o marketplace de
# pasta da 6d (`./.claude/harness/mod`, com o `--scope local`), e o mod se instala como os outros plugins.
ESCOPO_DA_INSTALACAO = "project"
COPIA_O_WORKFLOW = False
MOD_PELO_MARKETPLACE_DE_PASTA = False
REPOSITORIO_DO_PLUGIN = "Ela-Decora/ela-harness"
MARKETPLACE = "ela-harness"
LANCADOR = "modelo/lancador.py"
LANCADOR_NO_PROJETO = ".claude/harness/harness.py"
WORKFLOW = "workflows/revisao-do-bloco.js"
TEMPO_DO_CLAUDE = 60
TEMPO_DA_LISTA_DO_CLAUDE = 30
RAMO_PADRAO = "main"
BACKLOG_PADRAO = "docs/backlog"
BACKLOG_DO_MODELO = "docs/backlog/README.md"
MARCA_DO_NOME = "{{PROJETO}}"
MARCA_DA_DATA = "{{DATA}}"
# As linhas do `.gitignore` do modelo de desenvolvimento, que o item `.gitignore` do `conferir` confere.
LINHAS_DO_GITIGNORE = (
    ".claude/worktrees/", ".env", ".env.local", ".superpowers/", "__pycache__/", ".claude/settings.local.json",
    "**/.claude-plugin/types/", comum.LINK_DO_NUCLEO, ".harness-nucleo/",
)
PROXIMO = {
    PLANEJAMENTO: "próximo: escreva a ideia em planejamento/rascunho.md e as decisões fixas no CLAUDE.md; numa sessão "
                  "nova, rode harness.py ambiente e harness.py proximo",
    DESENVOLVIMENTO: "próximo: preencha .claude/perfil.toml e rode harness.py importar",
}


class ArquivoForaDoUtf8(UnicodeDecodeError):
    """O `UnicodeDecodeError` de um arquivo do repositório de código que não está em UTF-8, com o `caminho` dele
    relativo à raiz, para a mensagem nomear o arquivo."""

    def __init__(self, erro: UnicodeDecodeError, caminho: str):
        super().__init__(erro.encoding, erro.object, erro.start, erro.end, erro.reason)
        self.caminho = caminho


def motivo_do_utf8(erro: UnicodeDecodeError) -> str:
    """`<caminho>: arquivo fora do UTF-8`; o erro que não traz o caminho dá só `arquivo fora do UTF-8`."""
    caminho = getattr(erro, "caminho", None)
    return f"{caminho}: arquivo fora do UTF-8" if caminho else "arquivo fora do UTF-8"


def arquivos_do_modelo(modelo: Path) -> list[str]:
    """Os arquivos do modelo, relativos a ele, em posix e em ordem; o `__pycache__` fica de fora."""
    return sorted(
        arquivo.relative_to(modelo).as_posix()
        for arquivo in modelo.rglob("*")
        if arquivo.is_file() and "__pycache__" not in arquivo.parts
    )


def _ref_do_plugin() -> str:
    """A tag da versão do plugin, `v<version>` do `.claude-plugin/plugin.json`: a `ref` que o modelo fixa."""
    return "v" + json.loads(comum.ler_texto(ORIGEM / ".claude-plugin" / "plugin.json"))["version"]


def comandos_da_instalacao(trilha: str) -> tuple[tuple[str, ...], ...]:
    """Os comandos do `claude` que instalam os plugins da trilha: o `plugin marketplace add` do GitHub na tag da versão
    e um `plugin install <id>` por plugin, todos com o `ESCOPO_DA_INSTALACAO`."""
    escopo = ("--scope", ESCOPO_DA_INSTALACAO)
    return (("plugin", "marketplace", "add", f"{REPOSITORIO_DO_PLUGIN}#{_ref_do_plugin()}", *escopo),
            *(("plugin", "install", id_, *escopo) for id_ in PLUGINS[trilha]))


def linha_dos_comandos(trilha: str) -> str:
    """Os comandos da instalação, numa linha só, para quem os roda à mão."""
    return " e ".join("claude " + " ".join(comando) for comando in comandos_da_instalacao(trilha))


def _valores_do_perfil(destino: Path) -> tuple[str, str]:
    """O ramo principal e a pasta do backlog do `.claude/perfil.toml` do destino; sem o perfil legível, ou sem a
    chave, valem `main` e `docs/backlog`. O perfil é lido como TOML, sem validar."""
    try:
        dados = perfil_comum.ler_dados(destino / ".claude" / "perfil.toml")
    except (OSError, UnicodeDecodeError, perfil_comum.PerfilInvalido):
        return RAMO_PADRAO, BACKLOG_PADRAO
    desenvolvimento = dados.get("desenvolvimento")
    if not isinstance(desenvolvimento, dict):
        return RAMO_PADRAO, BACKLOG_PADRAO
    ramo = desenvolvimento.get("ramo_principal")
    caminhos = desenvolvimento.get("caminhos")
    backlog = caminhos.get("backlog") if isinstance(caminhos, dict) else None
    return (ramo if isinstance(ramo, str) and ramo else RAMO_PADRAO,
            backlog if isinstance(backlog, str) and backlog else BACKLOG_PADRAO)


def _recusar_antes_de_gravar(destino: Path, trilha: str, executar) -> None:
    """As três recusas, nesta ordem: sem o modelo ou o lançador no plugin, a pasta que não é a raiz de um repositório
    git e a que já tem o lançador."""
    for fonte in (ORIGEM / "modelo" / trilha, ORIGEM / LANCADOR):
        if not fonte.exists():
            raise bloco.Recusa(f"sem o modelo em {fonte}; reinstale o plugin")
    topo = bloco.git(destino, ["rev-parse", "--show-toplevel"], executar)
    if topo.returncode != 0 or Path(topo.stdout.decode("utf-8", "replace").strip()).resolve() != destino.resolve():
        raise bloco.Recusa(f"{destino} não é a raiz de um repositório git")
    if (destino / LANCADOR_NO_PROJETO).exists():
        raise bloco.Recusa(
            f"{destino} já tem o harness; atualizar o harness de um repositório já iniciado ainda não existe")


def _trocar(dados: bytes, trocas: tuple[tuple[str, str], ...]) -> bytes:
    """Os bytes com as marcas trocadas; o arquivo que não é texto em UTF-8 fica como está."""
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados
    for marca, valor in trocas:
        texto = texto.replace(marca, valor)
    return texto.encode("utf-8")


class _Copia:
    """A cópia sem sobrescrever: o que já existe no destino fica e entra na lista dos mantidos."""

    def __init__(self, destino: Path):
        self.destino = destino
        self.mantidos: list[str] = []

    def arquivo(self, fonte: Path, relativo: str, trocas: tuple[tuple[str, str], ...] = ()) -> None:
        alvo = self.destino / relativo
        if alvo.exists() or alvo.is_symlink():
            self.mantidos.append(relativo)
            return
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fonte, alvo)
        if trocas:
            alvo.write_bytes(_trocar(alvo.read_bytes(), trocas))


def _ler_da_equipe(destino: Path, relativo: str) -> str | None:
    """O texto do arquivo que a equipe já tem; sem ele, None. O fora do UTF-8 sai com o `ArquivoForaDoUtf8`."""
    if not (destino / relativo).exists():
        return None
    try:
        return comum.ler_texto(destino / relativo)
    except UnicodeDecodeError as erro:
        raise ArquivoForaDoUtf8(erro, relativo) from None


def _ler_settings_da_equipe(destino: Path) -> dict | None:
    """O `.claude/settings.json` que a pasta já tem, como objeto JSON; sem ele, None. O fora do UTF-8 sai com o
    `ArquivoForaDoUtf8`; o JSON malformado e o que não é objeto, com a `bloco.Recusa`."""
    texto = _ler_da_equipe(destino, _SETTINGS)
    if texto is None:
        return None
    corrija = f"{_SETTINGS}: {{}}; corrija o arquivo e rode o iniciar de novo"
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise bloco.Recusa(corrija.format(f"JSON malformado na linha {getattr(erro, 'lineno', 1)}")) from None
    if not isinstance(dados, dict):
        raise bloco.Recusa(corrija.format("não é um objeto JSON"))
    return dados


def mesclar_settings(existente: dict, do_modelo: dict) -> dict:
    """O `settings.json` da equipe com o do modelo, sem mudar o `existente`. Em cada lista do `permissions` do modelo,
    as regras que faltam vão para o fim, na ordem do modelo e sem repetir; a lista que falta é criada. As outras chaves
    do `permissions`, cada `extraKnownMarketplaces.<nome>` e cada `enabledPlugins.<id>` do modelo, e as outras chaves
    de topo, entram só se faltarem: o que a equipe já tem fica, como a `ref` que ela instalou."""
    mesclado = copy.deepcopy(existente)
    for chave, valor in do_modelo.items():
        if chave not in mesclado:
            mesclado[chave] = copy.deepcopy(valor)
            continue
        atual = mesclado[chave]
        if not (isinstance(atual, dict) and isinstance(valor, dict)):
            continue
        if chave == "permissions":
            for nome, regras in valor.items():
                if nome not in atual:
                    atual[nome] = copy.deepcopy(regras)
                elif isinstance(atual[nome], list) and isinstance(regras, list):
                    for regra in regras:
                        if regra not in atual[nome]:
                            atual[nome].append(copy.deepcopy(regra))
        elif chave in ("extraKnownMarketplaces", "enabledPlugins"):
            for nome, item in valor.items():
                atual.setdefault(nome, copy.deepcopy(item))
    return mesclado


def _settings(destino: Path, modelo: Path, trocas: tuple[tuple[str, str], ...], existente: dict) -> bool:
    """Grava no `.claude/settings.json` da equipe, de dados `existente`, o que falta do modelo, com as marcas já
    trocadas, em JSON com 2 espaços e `\\n` no fim. Devolve se gravou; sem nada a acrescentar, o arquivo fica."""
    do_modelo = json.loads(_trocar((modelo / _SETTINGS).read_bytes(), trocas).decode("utf-8"))
    mesclado = mesclar_settings(existente, do_modelo)
    if mesclado == existente:
        return False
    (destino / _SETTINGS).write_text(json.dumps(mesclado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _gitignore(destino: Path, modelo: Path, trocas: tuple[tuple[str, str], ...], texto: str | None) -> str | None:
    """Põe o `.gitignore` do modelo, ou acrescenta ao da equipe, de `texto`, só as linhas do modelo que faltam,
    começando numa linha nova. Devolve a linha da saída; com o `.gitignore` copiado do modelo, None."""
    alvo = destino / ".gitignore"
    if texto is None:
        _Copia(destino).arquivo(modelo / ".gitignore", ".gitignore", trocas)
        return None
    tem = {linha.strip() for linha in texto.splitlines()}
    do_modelo = _trocar((modelo / ".gitignore").read_bytes(), trocas).decode("utf-8").splitlines()
    faltam = [linha for linha in do_modelo if linha.strip() and linha.strip() not in tem]
    if not faltam:
        return ".gitignore: em dia"
    inicio = "" if not texto or texto.endswith("\n") else "\n"
    alvo.write_text(texto + inicio + "".join(linha + "\n" for linha in faltam), encoding="utf-8")
    return ".gitignore: 1 linha acrescentada" if len(faltam) == 1 else f".gitignore: {len(faltam)} linhas acrescentadas"


def _linha_do_mantido(modelo: Path, relativo: str, claude_md: str | None) -> str:
    """`mantido: <caminho>`. No `CLAUDE.md` mantido, de texto `claude_md`, a linha diz as linhas `@` do modelo que
    faltam nele: sem elas, os textos gerados não entram na sessão."""
    if relativo != "CLAUDE.md" or claude_md is None:
        return f"mantido: {relativo}"
    tem = {linha.strip() for linha in claude_md.splitlines()}
    faltam = [linha for linha in comum.ler_texto(modelo / relativo).splitlines()
              if linha.startswith("@") and linha not in tem]
    if not faltam:
        return f"mantido: {relativo}"
    return f"mantido: {relativo}; acrescente as linhas do modelo: {', '.join(faltam)}"


def _subcomando(comando: tuple[str, ...]) -> str:
    """Os nomes do comando do `claude`, sem os argumentos: `plugin marketplace add` ou `plugin install`."""
    return " ".join(comando[:3] if comando[1] == "marketplace" else comando[:2])


def _instalar_os_plugins(destino: Path, trilha: str, claude: str | None, executar) -> str:
    """Roda os comandos da instalação no destino; a linha da saída diz se instalou ou o que falta. Nunca recusa."""
    falta = "plugins: falta: {}; rode " + linha_dos_comandos(trilha)
    if claude is None:
        return falta.format("sem o claude no PATH")
    for comando in comandos_da_instalacao(trilha):
        try:
            feito = executar([claude, *comando], cwd=str(destino), capture_output=True, timeout=TEMPO_DO_CLAUDE)
        except OSError as erro:
            return falta.format(f"claude {_subcomando(comando)} não rodou: {comum.motivo_do_sistema(erro)}")
        except subprocess.SubprocessError:
            return falta.format(f"claude {_subcomando(comando)} passou de {TEMPO_DO_CLAUDE} s")
        if feito.returncode != 0:
            return falta.format(f"claude {_subcomando(comando)} saiu com {feito.returncode}")
    return "plugins: instalados nesta máquina"


def _ligar_os_githooks(destino: Path, executar) -> str:
    """Liga o `core.hooksPath` aos githooks; a linha da saída diz se ligou ou o que falta. Nunca recusa."""
    try:
        feito = bloco.git(destino, ["config", "core.hooksPath", ".githooks"], executar)
    except bloco.Recusa as erro:
        motivo = erro.mensagem
    else:
        if feito.returncode == 0:
            return "core.hooksPath: .githooks"
        motivo = comum.motivo_do_git(feito, "config")
    return f"core.hooksPath: falta: {motivo}; rode git config core.hooksPath .githooks"


def _gerar_o_planejamento(destino: Path, executar) -> list[str]:
    """O `gerar` da trilha de planejamento, sem o `harness.yml`, que o `iniciar` já tratou; o perfil que não vale, que a
    pasta já tinha, vira a linha do que falta."""
    try:
        gerador.gravar_o_planejamento(destino, executar, com_ci=False)
    except perfil_comum.PerfilInvalido as erro:
        return [f"gerado: falta: {_motivo(erro)}; corrija {_PERFIL} e rode harness.py gerar"]
    return [f"gerado: {gerador.PLANEJAMENTO}"]


def _settings_para_o_ci(destino: Path) -> str | None:
    """O texto do `.claude/settings.json` da pasta, None sem ele; o fora do UTF-8 sai com a recusa do `ci`."""
    try:
        return comum.ler_texto(destino / _SETTINGS)
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        raise ci.recusa_do_settings(ci.MOTIVO_FORA_DO_UTF8) from None


def _escrever_o_ci(destino: Path, trilha: str, ramo: str, mantidos: list[str]) -> list[str]:
    """Escreve o `harness.yml` da `trilha`, nas duas, com o `ramo` e a `ref` do settings já mesclado, pela função do
    gerador, sem depender de o perfil valer. O arquivo que já existe fica, e entra nos `mantidos`. A recusa de versão
    e a do settings viram a linha devolvida, e o arquivo não se grava."""
    alvo = destino / ci.CAMINHO
    if alvo.exists() or alvo.is_symlink():
        mantidos.append(ci.CAMINHO)
        return []
    try:
        textos = ci.gerar(lambda _: _settings_para_o_ci(destino), trilha, ramo, ci.versao_do_nucleo())
    except ci.RecusaDoCi as erro:
        return [erro.motivo]
    for relativo, texto in textos.items():
        comum.escrever_texto(destino / relativo, texto)
    return []


def iniciar(destino: Path, trilha: str, claude: str | None, nome: str | None = None, executar=subprocess.run,
            hoje: datetime.date | None = None) -> list[str]:
    """Copia o modelo da `trilha` e o lançador para o repositório `destino`, sem sobrescrever, troca as marcas, mescla
    o `.claude/settings.json` do modelo no que a pasta já tem (`mesclar_settings`), liga os githooks, instala os
    plugins e, no planejamento, roda o `gerar`, sem o `harness.yml`; esse arquivo o `iniciar` escreve nas duas trilhas
    (`_escrever_o_ci`) ou mantém, e a recusa dele vira uma linha da saída; devolve as linhas da saída. Lança
    `bloco.Recusa` antes de gravar qualquer coisa, também com o `.claude/settings.json` existente que não é um objeto JSON; a falha do
    `git config core.hooksPath` e a do `claude` nunca recusam."""
    _recusar_antes_de_gravar(destino, trilha, executar)
    # O que se lê da equipe vem antes da primeira escrita: com um arquivo fora do UTF-8, ou um `settings.json` que não
    # é objeto JSON, nada é gravado, e o `iniciar` roda de novo depois da correção.
    gitignore = _ler_da_equipe(destino, ".gitignore")
    claude_md = _ler_da_equipe(destino, "CLAUDE.md")
    settings = _ler_settings_da_equipe(destino)
    modelo = ORIGEM / "modelo" / trilha
    ramo, backlog = _valores_do_perfil(destino)
    trocas = ((MARCA_DO_NOME, nome or destino.resolve().name),
              (MARCA_DA_DATA, (hoje or datetime.date.today()).isoformat()))
    copia = _Copia(destino)
    relativos = arquivos_do_modelo(modelo)
    mesclados: list[str] = []
    for relativo in relativos:
        if relativo == ".gitignore":
            continue
        if relativo == _SETTINGS and settings is not None:
            if _settings(destino, modelo, trocas, settings):
                mesclados.append(relativo)
            else:
                copia.mantidos.append(relativo)
            continue
        alvo = f"{backlog}/README.md" if trilha == DESENVOLVIMENTO and relativo == BACKLOG_DO_MODELO else relativo
        copia.arquivo(modelo / relativo, alvo, trocas)
    recusas_do_ci = _escrever_o_ci(destino, trilha, ramo if trilha == DESENVOLVIMENTO else RAMO_PADRAO, copia.mantidos)
    copia.arquivo(ORIGEM / LANCADOR, LANCADOR_NO_PROJETO)
    os.chmod(destino / LANCADOR_NO_PROJETO, 0o755)
    com_workflow = COPIA_O_WORKFLOW and trilha == DESENVOLVIMENTO
    if com_workflow:
        copia.arquivo(ORIGEM / WORKFLOW, f".claude/{WORKFLOW}")
    linha_do_gitignore = _gitignore(destino, modelo, trocas, gitignore)
    mantidos = [_linha_do_mantido(modelo, relativo, claude_md) for relativo in copia.mantidos]
    linhas = [f"copiado: {len(relativos)} arquivos do modelo de {trilha} e o lançador"
              + (", e o workflow" if com_workflow else ""), *mantidos,
              *(f"mesclado: {relativo}" for relativo in mesclados)]
    if linha_do_gitignore is not None:
        linhas.append(linha_do_gitignore)
    linhas.append(_ligar_os_githooks(destino, executar))
    linhas.append(_instalar_os_plugins(destino, trilha, claude, executar))
    linhas += recusas_do_ci
    if trilha == PLANEJAMENTO:
        linhas += _gerar_o_planejamento(destino, executar)
    linhas.append(PROXIMO[trilha])
    return linhas


# Sem espaço logo depois do `<` nem logo antes do `>`: a redireção do shell (`< /dev/null > saida`) não é marcador.
_MARCADOR = re.compile(r"<[^<>\s](?:[^<>]*[^<>\s])?>")
_PERFIL = ".claude/perfil.toml"
_SETTINGS = ".claude/settings.json"
_CI = ci.CAMINHO
_GITHOOKS = ("pre-commit", "pre-push")
_SEM_PERFIL = "{}: falta: o perfil válido; resolva o item perfil primeiro"
_INICIAR_PELO_PLUGIN = f"rode /{comum.PREFIXO_DAS_SKILLS}iniciar {DESENVOLVIMENTO}"


def chaves_a_preencher(dados: dict, prefixo: str = "") -> list[str]:
    """As chaves cujo valor é um texto com um marcador `<...>`, inteiro ou no meio (`<org>/<repositório>`), com o
    caminho em pontos e na ordem do TOML. Numa lista, o índice entra a partir de 1, como em
    `desenvolvimento.verificacoes.1.comando`."""
    chaves: list[str] = []
    for chave, valor in dados.items():
        chaves += _marcadores(valor, f"{prefixo}.{chave}" if prefixo else str(chave))
    return chaves


def _marcadores(valor, caminho: str) -> list[str]:
    if isinstance(valor, str):
        return [caminho] if _MARCADOR.search(valor) else []
    if isinstance(valor, dict):
        return chaves_a_preencher(valor, caminho)
    if isinstance(valor, list):
        return [chave for numero, item in enumerate(valor, 1) for chave in _marcadores(item, f"{caminho}.{numero}")]
    return []


def _motivo(erro: perfil_comum.PerfilInvalido) -> str:
    return erro.mensagem.removeprefix("perfil inválido: ")


def _perfil(raiz: Path) -> tuple[str, perfil_desenvolvimento.PerfilDesenvolvimento | None]:
    """O item `perfil` e, com ele em dia, o perfil validado."""
    if not (raiz / _PERFIL).is_file():
        return f"perfil: falta: {_PERFIL}; {_INICIAR_PELO_PLUGIN}", None
    corrija = f"perfil: falta: {{}}; corrija {_PERFIL}"
    try:
        dados = perfil_comum.ler_dados(raiz / _PERFIL)
    except perfil_comum.PerfilInvalido as erro:
        return corrija.format(_motivo(erro)), None
    chaves = chaves_a_preencher(dados)
    if chaves:
        return f"perfil: falta: preencher {comum.juntar(chaves)}; edite {_PERFIL}", None
    try:
        return "perfil: ok", perfil_desenvolvimento.validar(dados)
    except perfil_comum.PerfilInvalido as erro:
        return corrija.format(_motivo(erro)), None


def _lista(valor) -> list:
    return valor if isinstance(valor, list) else []


def _marketplace_fixado(dados: dict) -> bool:
    """O `extraKnownMarketplaces.ela-harness` do GitHub `Ela-Decora/ela-harness`, com uma `ref` (spec do porte 1,
    §7.6)."""
    conhecidos = dados.get("extraKnownMarketplaces")
    marketplace = conhecidos.get(MARKETPLACE) if isinstance(conhecidos, dict) else None
    fonte = marketplace.get("source") if isinstance(marketplace, dict) else None
    return (isinstance(fonte, dict) and fonte.get("source") == "github" and fonte.get("repo") == REPOSITORIO_DO_PLUGIN
            and isinstance(fonte.get("ref"), str) and bool(fonte["ref"]))


def _item_plugin(raiz: Path) -> str:
    """O plugin fixado no `.claude/settings.json`, com os plugins da trilha no `enabledPlugins`, e o lançador."""
    corrija = f"plugin: falta: {_SETTINGS} legível ({{}}); corrija o arquivo"
    try:
        dados = json.loads(comum.ler_texto(raiz / _SETTINGS))
    except FileNotFoundError:
        return corrija.format("arquivo ausente")
    except UnicodeDecodeError:
        return corrija.format("fora do UTF-8")
    except OSError as erro:
        return corrija.format(comum.motivo_do_sistema(erro))
    except ValueError as erro:
        return corrija.format(f"JSON malformado na linha {getattr(erro, 'lineno', 1)}")
    if not isinstance(dados, dict):
        return corrija.format("não é um objeto JSON")
    faltam = [] if _marketplace_fixado(dados) else [
        f"extraKnownMarketplaces.{MARKETPLACE} (GitHub {REPOSITORIO_DO_PLUGIN}, com ref)"]
    ligados = dados.get("enabledPlugins")
    faltam += [f"enabledPlugins.{id_}" for id_ in PLUGINS[DESENVOLVIMENTO]
               if not (isinstance(ligados, dict) and ligados.get(id_) is True)]
    if faltam:
        return f"plugin: falta: {comum.juntar(faltam)} no {_SETTINGS}; rode {linha_dos_comandos(DESENVOLVIMENTO)}"
    if not (raiz / LANCADOR_NO_PROJETO).is_file():
        return f"plugin: falta: {LANCADOR_NO_PROJETO}, o lançador; {_INICIAR_PELO_PLUGIN}"
    return "plugin: ok"


def _item_githooks(raiz: Path, executar) -> str:
    atual = bloco.git(raiz, ["config", "--get", "core.hooksPath"], executar)
    if atual.stdout.decode("utf-8", "replace").strip() != ".githooks":
        return "githooks: falta: core.hooksPath em .githooks; rode git config core.hooksPath .githooks"
    for nome in _GITHOOKS:
        caminho = raiz / ".githooks" / nome
        if not caminho.is_file():
            return f"githooks: falta: .githooks/{nome}; {_INICIAR_PELO_PLUGIN}"
        if not os.access(caminho, os.X_OK):
            return f"githooks: falta: .githooks/{nome} executável; rode chmod +x .githooks/{nome}"
    return "githooks: ok"


def _item_gitignore(raiz: Path, perfil, executar) -> str:
    """As linhas fixas e, com o perfil válido, os arquivos da lane que o `lane abrir` confere (o `.env` do `env_modelo`
    e os `env_copiados`), pelo `git check-ignore`; o que falta vai na mesma linha."""
    try:
        tem = {linha.strip() for linha in comum.ler_texto(raiz / ".gitignore").splitlines()}
    except UnicodeDecodeError as erro:
        raise ArquivoForaDoUtf8(erro, ".gitignore") from None
    except OSError:
        tem = set()
    faltam = [linha for linha in LINHAS_DO_GITIGNORE if linha not in tem]
    if perfil is not None:
        import lane  # adiado: o lane importa o importacao, que importa este módulo
        faltam += [arquivo for arquivo in lane.nao_ignorados(raiz, perfil, executar) if arquivo not in faltam]
    if not faltam:
        return ".gitignore: ok"
    return f".gitignore: falta: {comum.juntar(faltam)}; acrescente-as ao .gitignore"


def _item_ci(raiz: Path, ramo: str) -> str:
    """O `harness.yml` igual ao gerado para o `ramo` e a `ref` do `.claude/settings.json`. Ausente ou diferente, a linha
    é a da falta; a recusa da versão ou a do settings dá a linha dela, sem o prefixo `harness.yml: `."""
    falta = f"ci: falta: {_CI} igual ao gerado; rode harness.py gerar"
    try:
        gerado = ci.gerar(lambda _: _settings_para_o_ci(raiz), DESENVOLVIMENTO, ramo, ci.versao_do_nucleo())
    except ci.RecusaDoCi as erro:
        return "ci: falta: " + erro.motivo[len(ci.PREFIXO):]
    except OSError:
        return falta
    try:
        igual = gerado.get(ci.CAMINHO) == comum.ler_texto(raiz / _CI)
    except (OSError, UnicodeDecodeError):
        return falta
    return "ci: ok" if igual else falta


def _item_passagem(raiz: Path, perfil, executar) -> str:
    """Como o `gerar --check`: a recusa do gerador e os gerados fora de dia."""
    try:
        textos = gerador.gerar(comum.leitor_do_disco(raiz), perfil)
        achados = gerador.problemas(textos, gerador.dados_do_disco(raiz), gerador.presentes_no_disco(raiz, executar))
    except gerador.GeracaoRecusada as erro:
        if erro.motivos[0].startswith("sem passagem"):
            return "passagem: falta: a passagem importada; rode harness.py importar"
        return f"passagem: falta: {erro.motivos[0]}; rode harness.py gerar --check"
    except bloco.Recusa as erro:
        return f"passagem: falta: {erro.mensagem}; rode harness.py gerar --check"
    if not achados:
        return "passagem: ok"
    return (f"passagem: falta: os gerados em dia ({len(achados)} problema{'' if len(achados) == 1 else 's'}); "
            "rode harness.py gerar")


def _item_invariantes(raiz: Path, perfil, executar) -> str:
    """As invariantes contra o `origin/<ramo>`, como o `invariantes --base`; sem a ref, não há o que comparar."""
    ref = f"origin/{perfil.ramo_principal}"
    try:
        existe = bloco.git(raiz, ["rev-parse", "--verify", "-q", f"refs/remotes/{ref}"], executar)
        if existe.returncode != 0:
            return f"invariantes: ok, sem {ref} para comparar"
        conferencias = invariantes.conferir(raiz, perfil, invariantes.BASE, ref, executar)
    except (bloco.Recusa, invariantes.ErroGit) as erro:
        motivo = getattr(erro, "mensagem", str(erro))
        return f"invariantes: falta: {motivo}; rode harness.py invariantes --base {ref} --verbose"
    for conferencia in conferencias:
        if not conferencia.ok:
            # O resumo de algumas conferências já traz o comando próprio; aqui vale o do item.
            resumo = conferencia.resumo.partition("; rode ")[0]
            return f"invariantes: falta: {resumo}; rode harness.py invariantes --base {ref} --verbose"
    return "invariantes: ok"


def _item_instalado(raiz: Path, claude: str | None, executar) -> str:
    """Os plugins da trilha habilitados para esta pasta ou para o usuário, pela lista do `claude plugin list --json`,
    que traz as instalações de todas as pastas da máquina."""
    rode = linha_dos_comandos(DESENVOLVIMENTO)
    a_mao = f"instalado: falta: conferir os plugins à mão, {{}}; rode {rode}"
    if claude is None:
        return a_mao.format("sem o claude no PATH")
    try:
        feito = executar([claude, "plugin", "list", "--json"], cwd=str(raiz), capture_output=True,
                         timeout=TEMPO_DA_LISTA_DO_CLAUDE)
    except OSError as erro:
        return a_mao.format(f"claude plugin list não rodou: {comum.motivo_do_sistema(erro)}")
    except subprocess.SubprocessError:
        return a_mao.format(f"claude plugin list passou de {TEMPO_DA_LISTA_DO_CLAUDE} s")
    if feito.returncode != 0:
        return a_mao.format(f"claude plugin list saiu com {feito.returncode}")
    try:
        instalados = json.loads(feito.stdout.decode("utf-8"))
    except ValueError:
        instalados = None
    if not isinstance(instalados, list):
        return a_mao.format("claude plugin list com saída ilegível")
    habilitados = {item.get("id") for item in instalados
                   if isinstance(item, dict) and item.get("enabled") is True
                   and (item.get("scope") == "user" or _desta_pasta(item.get("projectPath"), raiz))}
    faltam = [id_ for id_ in PLUGINS[DESENVOLVIMENTO] if id_ not in habilitados]
    if not faltam:
        return "instalado: ok"
    return (f"instalado: falta: {comum.juntar(faltam)} habilitado{'s' if len(faltam) > 1 else ''} nesta máquina; "
            f"rode {rode}")


def _item_linear(perfil, ambiente: Mapping[str, str]) -> str | None:
    """A chave no ambiente e a leitura do contexto no Linear, que traz o time, o projeto e os rótulos do perfil numa
    chamada só; sem a `[desenvolvimento.linear]`, `None`, e o `conferir` não ganha linha."""
    if perfil.linear is None:
        return None
    chave = linear.chave_do_ambiente(ambiente)
    if chave is None:
        return ("linear: falta: sem LINEAR_API_KEY no ambiente; ponha a chave no env do .claude/settings.local.json ou "
                "no ambiente da sessão")
    try:
        linear.ler_contexto(linear.Cliente(chave), perfil.linear)
    except linear.FalhaDoLinear as erro:
        motivo = " ".join(erro.mensagem.split())
        return f"linear: falta: {motivo}; confira o [desenvolvimento.linear] do perfil e a chave"
    return "linear: ok"


def _desta_pasta(caminho, raiz: Path) -> bool:
    try:
        return isinstance(caminho, str) and Path(caminho).resolve() == raiz.resolve()
    except (OSError, RuntimeError):
        return False


_DO_PRIMEIRO_COMMIT = (
    ".claude/harness", ".claude/workflows", ".claude/settings.json", ".claude/perfil.toml", ".githooks",
    ci.CAMINHO, ".gitignore", "CLAUDE.md",
)


def caminhos_do_primeiro_commit(raiz: Path, perfil) -> list[str]:
    """O que o `iniciar` deixou e o `importar` leva ao primeiro commit (spec 6d-repositorio, §7.3), na ordem do modelo
    e só o que existe em `raiz`: o lançador e os gerados, o workflow, os dois arquivos de `.claude`, os githooks, a CI,
    o `.gitignore`, o `CLAUDE.md` e o `README.md` da pasta do backlog do `perfil`. As skills e os agentes vêm do plugin
    (spec do porte 1, §7.5)."""
    candidatos = (*_DO_PRIMEIRO_COMMIT, f"{perfil.caminhos.backlog}/README.md")
    return [caminho for caminho in candidatos if (raiz / caminho).exists()]


def conferir(raiz: Path, claude: str | None, executar=subprocess.run,
             ambiente: Mapping[str, str] = os.environ) -> list[str]:
    """O que falta no repositório de código `raiz` para o primeiro bloco (spec 6d-repositorio, §7.4): uma linha por
    item, `<item>: ok` ou `<item>: falta: <o quê>; <comando>`. Um item que falha nunca impede os seguintes, e a
    função não lança. Com o perfil que não vale, os itens que dependem dele dizem isso. O item `linear` vem por último,
    só com a `[desenvolvimento.linear]` no perfil válido, e lê a chave do `ambiente`."""
    linha_do_perfil, perfil = _perfil(raiz)
    linhas = [linha_do_perfil, _item_plugin(raiz), _com_git(_item_githooks, raiz, "githooks", executar),
              _com_git(lambda r, e: _item_gitignore(r, perfil, e), raiz, ".gitignore", executar)]
    linhas.append(_item_ci(raiz, _valores_do_perfil(raiz)[0]))
    if perfil is None:
        linhas += [_SEM_PERFIL.format(item) for item in ("passagem", "invariantes")]
    else:
        linhas.append(_com_git(lambda r, e: _item_passagem(r, perfil, e), raiz, "passagem", executar))
        linhas.append(_com_git(lambda r, e: _item_invariantes(r, perfil, e), raiz, "invariantes", executar))
    linhas.append(_item_instalado(raiz, claude, executar))
    if perfil is not None:
        linha_do_linear = _item_linear(perfil, ambiente)
        if linha_do_linear is not None:
            linhas.append(linha_do_linear)
    return linhas


def _com_git(item, raiz: Path, nome: str, executar) -> str:
    """Roda o item que fala com o git; o git que não roda, o arquivo que não se lê e o fora do UTF-8 viram a linha
    `falta` do próprio item."""
    corrija = f"{nome}: falta: {{}}; corrija o caminho e rode harness.py iniciar --conferir de novo"
    try:
        return item(raiz, executar)
    except bloco.Recusa as erro:
        return f"{nome}: falta: {erro.mensagem}; rode o item de novo com o git funcionando"
    except UnicodeDecodeError as erro:
        return corrija.format(motivo_do_utf8(erro))
    except OSError as erro:
        motivo = comum.motivo_do_sistema(erro)
        return corrija.format(f"{erro.filename}: {motivo}" if erro.filename else motivo)
