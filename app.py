import streamlit as st
from gtts import gTTS
import io
import time
import random

# --- Configuração da Página ---
st.set_page_config(page_title="Mestre Lobisomem Pro", layout="centered", page_icon="🐺")

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 60px;
        font-size: 18px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    .stSelectbox label { font-size: 18px; font-weight: bold; }
    h1, h2, h3 { text-align: center; }
    .big-text { font-size: 24px; font-weight: bold; text-align: center; color: #d63031; }
    .info-text { font-size: 18px; text-align: center; color: #0984e3; }
    </style>
    """, unsafe_allow_html=True)

# --- Inicialização de Estado ---
DEFAULT_STATE = {
    'fase': 'setup',
    'jogadores': {},
    'temp_players': [],
    'config_papeis': [],
    'identificados': {}, 
    'audio_buffer': None,
    'turno': 1,
    'acoes_noite': {},
    'enamorados': [],
    'historico_mortes': [], 
    'transicao_dia_noite': False, 
    'vencedor': None,
    'qtd_lobos': 1,
    'erro_fatal': False,
    
    # Configs Avançadas
    'conf_bruxa_cura': 1,
    'conf_bruxa_veneno': 1,
    'conf_bruxa_cd': 0,
    'conf_anjo_uses': -1,
    'conf_anjo_cd': 1,
    'conf_medico_uses': 1,
    'conf_medico_cd': 0,
    
    'conf_fake_wake': True,
    'conf_fake_time_min': 5,
    'conf_fake_time_max': 10,
    'conf_revive_immunity': False,
    'conf_show_cause': False, 

    # Estado Habilidades
    'status_bruxa': {'cura': 1, 'veneno': 1},
    'status_bruxa_last_use': -99,
    'status_anjo_uses': -1,
    'status_anjo_last_use': -99,
    'status_medico_uses': 1,
    'status_medico_last_use': -99,
    
    'imunes_rodada': []
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Função de Voz ---
def falar(texto):
    try:
        texto_safe = ". " + texto 
        tts = gTTS(text=texto_safe, lang='pt')
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        st.session_state.audio_buffer = buffer
    except Exception as e:
        st.error(f"Erro audio: {e}")

# --- Helper de Cooldown ---
def check_cooldown(last_use, cd_config):
    turnos_desde = st.session_state.turno - last_use
    return turnos_desde <= cd_config

def format_uses(val):
    return "∞" if val == -1 else str(val)

# --- Verificação de Duplicidade Global ---
def verificar_duplicidade_global(novos_nomes):
    ocupados = []
    for papel, dono in st.session_state.identificados.items():
        if isinstance(dono, list): 
            ocupados.extend(dono)
        else:
            ocupados.append(dono)
    
    if not isinstance(novos_nomes, list):
        novos_nomes = [novos_nomes]
        
    for nome in novos_nomes:
        if nome in ocupados:
            return True
    return False

# --- Verificação de Vitória ---
def check_vitoria():
    vivos = [d for d in st.session_state.jogadores.values() if d['vivo']]
    qtd_lobos = sum(1 for p in vivos if p['papel'] in ['Lobisomens', 'Lobisomem Branco'])
    qtd_aldeia = len(vivos) - qtd_lobos
    
    if qtd_lobos == 0 and len(vivos) > 0:
        return "Aldeões"
    elif qtd_lobos >= qtd_aldeia and qtd_lobos > 0:
        return "Lobisomens"
    elif len(vivos) == 0:
        return "Empate (Todos Mortos)"
    return None

# --- Callback ---
def add_player_callback():
    nome = st.session_state.novo_jogador_input
    if nome and nome not in [p['nome'] for p in st.session_state.temp_players]:
        st.session_state.temp_players.append({'nome': nome, 'traco': 'Normal'})
    st.session_state.novo_jogador_input = "" 

# --- Reset Inteligente (Preserva Configs) ---
def reset_game():
    # Lista de chaves a DELETAR (Dados da partida atual)
    keys_to_delete = [
        'jogadores', 'identificados', 'config_papeis', 'audio_buffer', 
        'turno', 'acoes_noite', 'enamorados', 'historico_mortes', 
        'transicao_dia_noite', 'vencedor', 'qtd_lobos', 'erro_fatal',
        'imunes_rodada', 'victory_audio_played'
    ]
    
    # Deleta chaves dinâmicas
    all_keys = list(st.session_state.keys())
    for k in all_keys:
        if k in keys_to_delete or k.startswith('status_') or k.startswith('ident_req_') or k.startswith('turn_') or k.startswith('called_') or k.startswith('sel_lobo_'):
            del st.session_state[k]
            
    st.session_state.fase = 'setup'
    st.rerun()

# --- Sidebar (Controle) ---
with st.sidebar:
    st.header("Controle")
    if st.button("🔴 Encerrar/Reiniciar Partida"):
        reset_game()

# --- Textos Personalizados ---
TEXTOS_TRACOS = {
    "Normal": "foi encontrado sem vida",
    "Dramático": "fez sua última cena",
    "Rico": "deixou sua herança para ninguém",
    "Corajoso": "caiu lutando",
    "Misterioso": "deixou de existir",
    "Bêbado": "morreu abraçado a um barril"
}

# --- LÓGICA DO JOGO ---

# 0. TELA DE ERRO FATAL
if st.session_state.erro_fatal:
    st.error("ERRO CRÍTICO: JOGO ENCERRADO")
    st.markdown("### A mesma pessoa foi atribuída a duas profissões diferentes.")
    if st.session_state.audio_buffer:
        st.audio(st.session_state.audio_buffer, format='audio/mp3', autoplay=True)
    
    if st.button("Reiniciar Jogo"):
        reset_game()
    st.stop()

# 0.5 TELA DE VITÓRIA
elif st.session_state.get('vencedor'):
    if not st.session_state.get('victory_audio_played'):
        falar(f"Fim de jogo! Vitória dos {st.session_state.vencedor}!")
        st.session_state.victory_audio_played = True
        st.rerun()

    if st.session_state.audio_buffer:
        st.audio(st.session_state.audio_buffer, format='audio/mp3', autoplay=True)

    st.balloons()
    st.title(f"🏆 Vitória: {st.session_state.vencedor}!")
    st.markdown("<h3 style='text-align: center;'>A partida acabou.</h3>", unsafe_allow_html=True)
    
    if st.button("Jogar Novamente"):
        reset_game()
    st.stop()

# 1. TELA DE SETUP
elif st.session_state.fase == 'setup':
    st.title("🐺 Configuração da Partida")
    
    with st.expander("📝 Jogadores", expanded=True):
        st.text_input("Nome do Jogador (Enter para adicionar)", key="novo_jogador_input", on_change=add_player_callback)
        
        if 'temp_players' in st.session_state:
            for i, p in enumerate(st.session_state.temp_players):
                cols = st.columns([2, 2, 1])
                cols[0].write(f"**{p['nome']}**")
                p['traco'] = cols[1].selectbox(f"Traço {i}", ["Normal", "Dramático", "Rico", "Corajoso", "Misterioso", "Bêbado"], key=f"t{i}", label_visibility="collapsed")
                if cols[2].button("🗑️", key=f"d{i}"):
                    st.session_state.temp_players.pop(i)
                    st.rerun()
            st.caption(f"Total: {len(st.session_state.temp_players)} jogadores")

    st.divider()
    
    st.subheader("Cartas em Jogo")
    col_a, col_b = st.columns(2)
    with col_a:
        # Adicionados 'key' para persistência
        c_lobos = st.number_input("Qtd. Lobisomens", 1, 5, 1, key="cfg_lobos")
        tem_medico = st.checkbox("Médico", False, key="cfg_medico")
        tem_anjo = st.checkbox("Anjo", False, key="cfg_anjo")
        tem_bruxa = st.checkbox("Bruxa", False, key="cfg_bruxa")
    with col_b:
        tem_vidente = st.checkbox("Vidente", False, key="cfg_vidente")
        tem_cupido = st.checkbox("Cupido", False, key="cfg_cupido")
        tem_cacador = st.checkbox("Caçador", False, key="cfg_cacador")
        tem_branco = st.checkbox("Lobo Branco", False, key="cfg_branco")

    with st.expander("⚙️ Configurações Avançadas"):
        st.write("### 🧙‍♀️ Bruxa")
        c1, c2, c3 = st.columns(3)
        with c1:
            inf_cura = st.checkbox("Inf. Cura", key="inf_b_cura")
            val_cura = st.number_input("Qtd. Cura", 0, 5, 1, disabled=inf_cura)
            st.session_state.conf_bruxa_cura = -1 if inf_cura else val_cura
        with c2:
            inf_veneno = st.checkbox("Inf. Veneno", key="inf_b_veneno")
            val_veneno = st.number_input("Qtd. Veneno", 0, 5, 1, disabled=inf_veneno)
            st.session_state.conf_bruxa_veneno = -1 if inf_veneno else val_veneno
        st.session_state.conf_bruxa_cd = c3.selectbox("Cooldown", [0, 1, 2], index=0, format_func=lambda x: f"{x} Turnos" if x > 0 else "Sem CD", key="cd_bruxa")

        st.divider()
        st.write("### 🚑 Médico")
        c1, c2, c3 = st.columns(3)
        with c1: inf_med = st.checkbox("Infinito", key="inf_med")
        with c2:
            val_med = st.number_input("Ressurreições", 0, 10, 1, disabled=inf_med)
            st.session_state.conf_medico_uses = -1 if inf_med else val_med
        st.session_state.conf_medico_cd = c3.selectbox("Cooldown", [0, 1, 2], index=0, format_func=lambda x: f"{x} Turnos" if x > 0 else "Sem CD", key="cd_med")

        st.divider()
        st.write("### 👼 Anjo")
        c1, c2, c3 = st.columns(3)
        with c1: inf_anjo = st.checkbox("Infinito", value=True, key="inf_anjo")
        with c2:
             val_anjo = st.number_input("Proteções", 0, 10, 1, disabled=inf_anjo)
             st.session_state.conf_anjo_uses = -1 if inf_anjo else val_anjo
        st.session_state.conf_anjo_cd = c3.selectbox("Cooldown", [0, 1, 2], index=1, format_func=lambda x: f"{x} Turnos" if x > 0 else "Sem CD", key="cd_anjo")
        
        st.divider()
        st.write("### 🎭 Mecânicas")
        st.session_state.conf_show_cause = st.checkbox("Mostrar Causa da Morte", value=False, key="cfg_show_cause")
        st.session_state.conf_revive_immunity = st.checkbox("Imunidade ao reviver", value=False, key="cfg_revive_imun")
        st.session_state.conf_fake_wake = st.checkbox("Fake Wake", value=True, key="cfg_fake_wake")
        if st.session_state.conf_fake_wake:
            cm1, cm2 = st.columns(2)
            st.session_state.conf_fake_time_min = cm1.number_input("Tempo Min (s)", 1, 30, 5, key="cfg_time_min")
            st.session_state.conf_fake_time_max = cm2.number_input("Tempo Max (s)", 1, 60, 10, key="cfg_time_max")

    if st.button("INICIAR A NOITE", type="primary"):
        total_jogadores = len(st.session_state.temp_players)
        roles_count = c_lobos
        if tem_branco: roles_count += 1
        if tem_medico: roles_count += 1
        if tem_anjo: roles_count += 1
        if tem_bruxa: roles_count += 1
        if tem_vidente: roles_count += 1
        if tem_cupido: roles_count += 1
        if tem_cacador: roles_count += 1
        
        if total_jogadores < 4:
            st.error("Mínimo de 4 jogadores para iniciar!")
        elif roles_count > total_jogadores:
            st.error(f"Configuração inválida: Você selecionou {roles_count} papéis especiais/lobos para apenas {total_jogadores} jogadores!")
        else:
            st.session_state.jogadores = {p['nome']: {'vivo': True, 'traco': p['traco'], 'papel': 'Desconhecido'} for p in st.session_state.temp_players}
            st.session_state.qtd_lobos = c_lobos 
            
            st.session_state.status_bruxa = {'cura': st.session_state.conf_bruxa_cura, 'veneno': st.session_state.conf_bruxa_veneno}
            st.session_state.status_bruxa_last_use = -99
            st.session_state.status_medico_uses = st.session_state.conf_medico_uses
            st.session_state.status_medico_last_use = -99
            st.session_state.status_anjo_uses = st.session_state.conf_anjo_uses
            st.session_state.status_anjo_last_use = -99
            
            ordem = []
            if tem_medico: ordem.append('Médico')
            if tem_cupido: ordem.append('Cupido')
            if tem_anjo: ordem.append('Anjo')
            ordem.append('Lobisomens')
            if tem_branco: ordem.append('Lobisomem Branco')
            if tem_bruxa: ordem.append('Bruxa')
            if tem_vidente: ordem.append('Vidente')
            if tem_cacador: ordem.append('Caçador')
            
            st.session_state.config_papeis = ordem
            st.session_state.fase = 'noite'
            st.session_state.subfase = 'inicio'
            falar("A noite cai na vila. Todos dormem. Fechem os olhos.")
            st.rerun()

# 2. FASE DA NOITE
elif st.session_state.fase == 'noite':
    st.title(f"Lua Cheia - Noite {st.session_state.turno}")
    
    if st.session_state.audio_buffer:
        st.audio(st.session_state.audio_buffer, format='audio/mp3', start_time=0, autoplay=True)
    
    ordem = st.session_state.config_papeis
    
    # --- AUTOMATIZAÇÃO DO INÍCIO DA NOITE ---
    if st.session_state.subfase == 'inicio':
        st.session_state.acoes_noite = {
            'alvos_lobos': [],
            'protegido_anjo': None,
            'mortos_finais': [], 
            'ressuscitados': []
        }
        st.session_state.imunes_rodada = []
        
        st.info("A cidade dorme... Preparando turnos.")
        
        # Tempo aumentado para não cortar o áudio inicial
        time.sleep(7) 
        st.session_state.audio_buffer = None
        
        st.session_state.idx_papel = 0
        st.session_state.subfase = 'rodando'
        st.rerun()

    elif st.session_state.subfase == 'rodando':
        idx = st.session_state.idx_papel
        
        # --- AMANHECER AUTOMÁTICO ---
        if idx >= len(ordem):
            st.info("A noite acabou. O sol nasce...")
            time.sleep(2) 
            st.session_state.audio_buffer = None
            st.session_state.fase = 'dia'
            st.rerun()
        
        papel_atual = ordem[idx]
        
        # --- Lógica de Identificação ---
        precisa_id = True
        if papel_atual == 'Cupido': precisa_id = False
        
        # --- CASO ESPECIAL: LOBISOMENS (GRUPO) ---
        if papel_atual == 'Lobisomens':
            if 'Lobisomens' not in st.session_state.identificados:
                st.subheader("Alcateia")
                
                if "ident_req_alcateia" not in st.session_state:
                    falar("Lobisomens, acordem e identifiquem-se na tela.")
                    st.session_state["ident_req_alcateia"] = True
                    st.rerun()
                
                st.write("Selecione os jogadores que são Lobisomens:")
                qtd = st.session_state.qtd_lobos
                
                todos_nomes = list(st.session_state.jogadores.keys())
                lobos_selecionados = []
                
                cols = st.columns(qtd) if qtd <= 3 else [st.empty() for _ in range(qtd)]
                for i in range(qtd):
                    with (cols[i] if qtd <= 3 else st.container()):
                        l = st.selectbox(f"Lobo {i+1}", todos_nomes, key=f"sel_lobo_{i}", index=None, placeholder="Selecione...")
                        lobos_selecionados.append(l)
                
                if st.button("Confirmar Alcateia"):
                    if any(l is None for l in lobos_selecionados):
                        st.error("Selecione todos os lobisomens.")
                        st.stop()
                        
                    if len(set(lobos_selecionados)) != len(lobos_selecionados):
                        falar("Erro: Mesma pessoa com duas profissões.")
                        st.session_state.erro_fatal = True
                        st.rerun()
                    
                    if verificar_duplicidade_global(lobos_selecionados):
                        falar("Erro: Mesma pessoa com duas profissões.")
                        st.session_state.erro_fatal = True
                        st.rerun()
                    
                    for l in lobos_selecionados:
                        st.session_state.jogadores[l]['papel'] = 'Lobisomens'
                    st.session_state.identificados['Lobisomens'] = lobos_selecionados 
                    falar("Alcateia reconhecida.")
                    st.rerun()
                st.stop() 

        # --- CASO PADRÃO: PAPEIS ÚNICOS ---
        else:
            quem_eh_nome = st.session_state.identificados.get(papel_atual)
            if precisa_id and quem_eh_nome is None:
                st.subheader(f"Chamando {papel_atual}...")
                
                if f"ident_req_{papel_atual}" not in st.session_state:
                    falar(f"{papel_atual}, acorde e identifique-se.")
                    st.session_state[f"ident_req_{papel_atual}"] = True
                    st.rerun()
                    
                disponiveis = list(st.session_state.jogadores.keys())
                novo_dono = st.selectbox(f"Quem é o {papel_atual}?", disponiveis, index=None, placeholder="Selecione...")
                
                if st.button("Confirmar Identidade") and novo_dono:
                    if verificar_duplicidade_global(novo_dono):
                        falar("Erro: Mesma pessoa com duas profissões.")
                        st.session_state.erro_fatal = True
                        st.rerun()
                    
                    st.session_state.identificados[papel_atual] = novo_dono
                    st.session_state.jogadores[novo_dono]['papel'] = papel_atual
                    falar(f"{papel_atual} identificado.")
                    st.rerun()
                st.stop()

        # --- Lógica de Vida ---
        esta_vivo = True
        if precisa_id:
            if papel_atual == 'Lobisomens':
                lobos_vivos = [p for p in st.session_state.jogadores.values() if p['papel'] == 'Lobisomens' and p['vivo']]
                if not lobos_vivos:
                     esta_vivo = False
            else:
                quem_eh_nome = st.session_state.identificados.get(papel_atual)
                if quem_eh_nome:
                    esta_vivo = st.session_state.jogadores[quem_eh_nome]['vivo']

        # --- LÓGICA DE CHAMADA AUTOMÁTICA ---
        turn_key = f"turn_{st.session_state.turno}_{papel_atual}"
        if turn_key not in st.session_state:
            time.sleep(1.5) 
            if papel_atual == 'Lobisomens':
                falar("Lobisomens, acordem.")
            else:
                falar(f"{papel_atual}, acorde.")
            st.session_state[turn_key] = True
            st.rerun()

        # FAKE WAKE (Morto)
        if not esta_vivo:
            if st.session_state.conf_fake_wake:
                if 'fake_wake_start' not in st.session_state:
                    st.session_state.fake_wake_start = time.time()
                    tempo_espera = random.randint(st.session_state.conf_fake_time_min, st.session_state.conf_fake_time_max)
                    st.session_state.fake_wake_duration = tempo_espera
                    st.rerun()
                
                st.warning(f"⚠️ {papel_atual} está morto.")
                st.info(f"Simulando tempo de ação... ({int(st.session_state.fake_wake_duration)}s)")
                
                elapsed = time.time() - st.session_state.fake_wake_start
                if elapsed > st.session_state.fake_wake_duration:
                    falar(f"{papel_atual}, dorme.")
                    del st.session_state.fake_wake_start
                    del st.session_state.fake_wake_duration
                    st.session_state.idx_papel += 1
                    st.rerun()
                else:
                    time.sleep(0.5)
                    st.rerun()
            else:
                st.error(f"{papel_atual} está morto.")
                time.sleep(1)
                st.session_state.idx_papel += 1
                st.rerun()
            st.stop()

        # --- AÇÕES VIVAS ---
        st.subheader(f"Vez de: {papel_atual}")
        
        # 1. MÉDICO
        if papel_atual == 'Médico':
            uses = st.session_state.status_medico_uses
            em_cd = check_cooldown(st.session_state.status_medico_last_use, st.session_state.conf_medico_cd)
            
            st.write(f"Ressurreições: {format_uses(uses)} | CD: {'🔴 Em Recarga' if em_cd else '🟢 Pronto'}")
            
            mortos = [n for n, d in st.session_state.jogadores.items() if not d['vivo']]
            tem_usos = (uses == -1 or uses > 0)
            
            if tem_usos and mortos and not em_cd:
                usar = st.radio("Usar habilidade?", ["Não", "Sim"], horizontal=True)
                if usar == "Sim":
                    alvo = st.selectbox("Quem reviver?", mortos, index=None, placeholder="Escolha...")
                    if st.button("Reviver") and alvo:
                        st.session_state.acoes_noite['ressuscitados'].append(alvo)
                        if st.session_state.status_medico_uses != -1:
                            st.session_state.status_medico_uses -= 1
                        st.session_state.status_medico_last_use = st.session_state.turno
                        if st.session_state.conf_revive_immunity:
                            st.session_state.imunes_rodada.append(alvo)
                        st.success("Feito.")
                        falar("Médico, dorme.")
                        time.sleep(0.5)
                        st.session_state.idx_papel += 1
                        st.rerun()
                else:
                    if st.button("Dormir sem agir"): 
                        falar("Médico, dorme.")
                        time.sleep(0.5)
                        st.session_state.idx_papel += 1; st.rerun()
            else:
                st.info("Sem ação disponível.")
                if st.button("Dormir"): 
                    falar("Médico, dorme.")
                    time.sleep(0.5)
                    st.session_state.idx_papel += 1; st.rerun()

        # 2. CUPIDO
        elif papel_atual == 'Cupido':
            if st.session_state.turno == 1:
                st.write("Escolha o casal:")
                vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo']]
                a1 = st.selectbox("Amor 1", vivos, index=None, placeholder="Pessoa 1")
                a2 = st.selectbox("Amor 2", [v for v in vivos if v != a1], index=None, placeholder="Pessoa 2")
                if st.button("Unir") and a1 and a2:
                    st.session_state.enamorados = [a1, a2]
                    st.success("Casal unido!")
                    falar("Cupido, dorme.")
                    time.sleep(0.5)
                    st.session_state.idx_papel += 1
                    st.rerun()
            else:
                st.info("Cupido já agiu.")
                time.sleep(1)
                st.session_state.idx_papel += 1; st.rerun()

        # 3. ANJO
        elif papel_atual == 'Anjo':
            em_cd = check_cooldown(st.session_state.status_anjo_last_use, st.session_state.conf_anjo_cd)
            uses = st.session_state.status_anjo_uses
            
            st.write(f"Proteções: {format_uses(uses)} | CD: {'🔴 Em Recarga' if em_cd else '🟢 Pronto'}")
            tem_usos = (uses == -1 or uses > 0)
            
            if not em_cd and tem_usos:
                usar = st.radio("Proteger alguém?", ["Não", "Sim"], horizontal=True)
                if usar == "Sim":
                    vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo']]
                    alvo = st.selectbox("Quem?", vivos, index=None, placeholder="Escolha...")
                    if st.button("Proteger") and alvo:
                        st.session_state.acoes_noite['protegido_anjo'] = alvo
                        st.session_state.status_anjo_last_use = st.session_state.turno
                        if st.session_state.status_anjo_uses != -1:
                            st.session_state.status_anjo_uses -= 1
                        falar("Anjo, dorme.")
                        time.sleep(0.5)
                        st.session_state.idx_papel += 1
                        st.rerun()
                else:
                    if st.button("Dormir"): 
                        falar("Anjo, dorme.")
                        time.sleep(0.5)
                        st.session_state.idx_papel += 1; st.rerun()
            else:
                st.warning("Em recarga ou sem usos.")
                if st.button("Dormir"): 
                    falar("Anjo, dorme.")
                    time.sleep(0.5)
                    st.session_state.idx_papel += 1; st.rerun()

        # 4. LOBISOMENS
        elif papel_atual == 'Lobisomens':
            vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo']]
            st.write("Escolham a vítima.")
            vitima = st.selectbox("Vítima:", vivos, index=None, placeholder="Selecione...")
            if st.button("Matar") and vitima:
                st.session_state.acoes_noite['alvos_lobos'].append(vitima)
                falar("Lobisomens dormem.")
                time.sleep(0.5)
                st.session_state.idx_papel += 1
                st.rerun()

        # 5. LOBO BRANCO
        elif papel_atual == 'Lobisomem Branco':
            if st.session_state.turno % 2 == 0:
                usar = st.radio("Trair a alcateia hoje?", ["Não", "Sim"], horizontal=True)
                if usar == "Sim":
                    vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo']]
                    alvo = st.selectbox("Alvo:", vivos, index=None, placeholder="Selecione...")
                    if st.button("Matar") and alvo:
                        # Lobo branco age como uma facção separada aqui para simplificar, mas entra na lista de mortos
                        st.session_state.acoes_noite['mortos_finais'].append((alvo, "Ataque do Lobo Branco"))
                        falar("Lobo branco, dorme.")
                        time.sleep(0.5)
                        st.session_state.idx_papel += 1
                        st.rerun()
                else:
                    if st.button("Dormir"): 
                        falar("Lobo branco, dorme.")
                        time.sleep(0.5)
                        st.session_state.idx_papel += 1; st.rerun()
            else:
                st.info("Apenas observa.")
                time.sleep(1)
                st.session_state.idx_papel += 1; st.rerun()

        # 6. BRUXA
        elif papel_atual == 'Bruxa':
            vitimas = st.session_state.acoes_noite['alvos_lobos']
            st.info(f"Vítimas dos lobos: {', '.join(vitimas) if vitimas else 'Ninguém'}")
            
            em_cd = check_cooldown(st.session_state.status_bruxa_last_use, st.session_state.conf_bruxa_cd)
            
            st.write(f"CD: {'🔴 Em Recarga' if em_cd else '🟢 Pronto'}")
            st.write(f"Estoques: ❤️ {format_uses(st.session_state.status_bruxa['cura'])} | ☠️ {format_uses(st.session_state.status_bruxa['veneno'])}")
            
            if not em_cd:
                # Poção Vida
                usou_cura = False
                qtd_cura = st.session_state.status_bruxa['cura']
                pode_curar = (qtd_cura == -1 or qtd_cura > 0)

                if pode_curar and vitimas:
                    if st.radio("Usar Cura?", ["Não", "Sim"], horizontal=True, key="b_cura") == "Sim":
                        salvo = st.selectbox("Salvar quem?", vitimas, index=None, placeholder="Escolha...")
                        if st.button("Curar") and salvo:
                            st.session_state.acoes_noite['alvos_lobos'].remove(salvo)
                            if st.session_state.status_bruxa['cura'] != -1:
                                st.session_state.status_bruxa['cura'] -= 1
                            st.session_state.status_bruxa_last_use = st.session_state.turno
                            usou_cura = True
                            st.success("Curado.")
                
                # Poção Morte
                qtd_veneno = st.session_state.status_bruxa['veneno']
                pode_matar = (qtd_veneno == -1 or qtd_veneno > 0)

                if pode_matar:
                    if st.radio("Usar Veneno?", ["Não", "Sim"], horizontal=True, key="b_veneno") == "Sim":
                        vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo']]
                        alvo_m = st.selectbox("Matar quem?", vivos, index=None, placeholder="Escolha...")
                        if st.button("Envenenar") and alvo_m:
                            st.session_state.acoes_noite['mortos_finais'].append((alvo_m, "Poção da Bruxa"))
                            if st.session_state.status_bruxa['veneno'] != -1:
                                st.session_state.status_bruxa['veneno'] -= 1
                            if not usou_cura:
                                st.session_state.status_bruxa_last_use = st.session_state.turno
                            st.success("Feito.")
            else:
                st.warning("A bruxa está recuperando suas energias.")
            
            if st.button("Dormir"):
                falar("Bruxa, dorme.")
                time.sleep(0.5)
                st.session_state.idx_papel += 1
                st.rerun()

        # 7. VIDENTE
        elif papel_atual == 'Vidente':
            alvo = st.selectbox("Investigar:", list(st.session_state.jogadores.keys()), index=None, placeholder="Escolha...")
            
            if 'vidente_revealed' not in st.session_state:
                st.session_state.vidente_revealed = None

            if st.button("Revelar (Silencioso)") and alvo:
                role_real = st.session_state.jogadores[alvo].get('papel', 'Desconhecido')
                role_mostrada = role_real
                if role_real in ['Cupido', 'Caçador', 'Aldeão', 'Anjo', 'Médico']:
                    role_mostrada = "Aldeão"
                
                st.session_state.vidente_revealed = f"A carta de {alvo} é: {role_mostrada}"
            
            if st.session_state.vidente_revealed:
                st.markdown(f"<div class='big-text'>{st.session_state.vidente_revealed}</div>", unsafe_allow_html=True)
                st.caption("Apenas você está vendo isso.")

            if st.button("Dormir"):
                st.session_state.vidente_revealed = None
                falar("Vidente, dorme.")
                time.sleep(0.5)
                st.session_state.idx_papel += 1
                st.rerun()
        
        # 8. CAÇADOR (Apenas Identificação e Dormir)
        elif papel_atual == 'Caçador':
            st.info("O Caçador dorme tranquilamente, com a arma ao lado.")
            if st.button("Dormir"):
                falar("Caçador, dorme.")
                time.sleep(0.5)
                st.session_state.idx_papel += 1
                st.rerun()

# 3. FASE DO DIA
elif st.session_state.fase == 'dia':
    
    # Checagem de Vitória ao amanhecer
    ganhador = check_vitoria()
    if ganhador:
        st.session_state.vencedor = ganhador
        st.rerun()

    # Player Principal (só toca se não estiver em transição)
    if st.session_state.audio_buffer and not st.session_state.transicao_dia_noite:
        st.audio(st.session_state.audio_buffer, format='audio/mp3', autoplay=True)

    # Processamento Lógica do Amanhecer
    if 'processado_dia' not in st.session_state or st.session_state.processado_dia != st.session_state.turno:
        # (Nome, Causa)
        mortos_hoje_com_causa = []
        
        # 1. Ressurreições
        for revivido in st.session_state.acoes_noite['ressuscitados']:
            st.session_state.jogadores[revivido]['vivo'] = True

        # 2. Mortes Lobos
        for alvo in st.session_state.acoes_noite['alvos_lobos']:
            protegido_anjo = (alvo == st.session_state.acoes_noite['protegido_anjo'])
            imune_revive = (alvo in st.session_state.imunes_rodada)
            if not protegido_anjo and not imune_revive:
                mortos_hoje_com_causa.append((alvo, "Ataque de Lobisomem"))
        
        # 2.1 Vingança Automática do Caçador
        for (morto, causa) in mortos_hoje_com_causa:
            papel_morto = st.session_state.jogadores[morto].get('papel')
            if papel_morto == 'Caçador' and "Lobisomem" in causa:
                lobos_vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo'] and d['papel'] == 'Lobisomens']
                if lobos_vivos:
                    lobo_azarado = random.choice(lobos_vivos)
                    if lobo_azarado not in [m[0] for m in mortos_hoje_com_causa]:
                         mortos_hoje_com_causa.append((lobo_azarado, "Tiro Reflexo do Caçador"))

        # 3. Mortos Finais (Bruxa, Lobo Branco)
        for (alvo, causa) in st.session_state.acoes_noite['mortos_finais']:
            if alvo not in [m[0] for m in mortos_hoje_com_causa]:
                mortos_hoje_com_causa.append((alvo, causa))

        # 4. Enamorados
        novos = True
        while novos:
            novos = False
            if st.session_state.enamorados:
                a1, a2 = st.session_state.enamorados
                m1_morto = (a1 in [m[0] for m in mortos_hoje_com_causa] or not st.session_state.jogadores[a1]['vivo'])
                m2_morto = (a2 in [m[0] for m in mortos_hoje_com_causa] or not st.session_state.jogadores[a2]['vivo'])
                
                if m1_morto and not m2_morto:
                    mortos_hoje_com_causa.append((a2, f"Morreu de amor por {a1}"))
                    novos = True
                if m2_morto and not m1_morto:
                    mortos_hoje_com_causa.append((a1, f"Morreu de amor por {a2}"))
                    novos = True

        # Narrativa
        narracao = "A cidade acorda. "
        
        if st.session_state.acoes_noite['ressuscitados']:
            nomes_res = [n for n in st.session_state.acoes_noite['ressuscitados'] if n not in [m[0] for m in mortos_hoje_com_causa]]
            if nomes_res:
                narracao += f"Um milagre! {', '.join(nomes_res)} voltou à vida! "

        if not mortos_hoje_com_causa:
            narracao += "Ninguém morreu esta noite!"
        else:
            for (m, causa) in mortos_hoje_com_causa:
                st.session_state.jogadores[m]['vivo'] = False
                traco = st.session_state.jogadores[m]['traco']
                desc_traco = TEXTOS_TRACOS.get(traco, "morreu")
                
                # Verifica Configuração de Mostrar Causa
                if st.session_state.conf_show_cause:
                    narracao += f"{m} {desc_traco}. Causa: {causa}. "
                else:
                    narracao += f"{m} {desc_traco}. "
        
        falar(narracao)
        st.session_state.texto_dia = narracao
        st.session_state.processado_dia = st.session_state.turno
        st.rerun() 

    st.title("☀️ Amanhecer")
    st.write(st.session_state.texto_dia)

    st.divider()
    
    # Transição de Dia para Noite
    if st.session_state.transicao_dia_noite:
        st.warning("⚠️ Preparando para anoitecer...")
        # Tempo reduzido de transição
        time.sleep(5) 
        
        # Check Vitoria pós-votação
        ganhador = check_vitoria()
        if ganhador:
            st.session_state.vencedor = ganhador
            st.rerun()

        st.session_state.transicao_dia_noite = False
        st.session_state.turno += 1
        st.session_state.fase = 'noite'
        st.session_state.subfase = 'inicio'
        st.rerun()
        
    else:
        st.header("Votação")
        vivos = [n for n, d in st.session_state.jogadores.items() if d['vivo']]
        if not vivos:
            st.error("Todos morreram.") # Fallback caso check_vitoria falhe
            
        votado = st.selectbox("Quem eliminar?", ["Pular"] + vivos)
        
        if st.button("Confirmar Votação"):
            if votado != "Pular":
                st.session_state.jogadores[votado]['vivo'] = False
                falar(f"A vila eliminou {votado}. Causa da morte: Sentença da Vila.")
            else:
                falar("Ninguém foi eliminado.")
            
            # Ativa modo de transição
            st.session_state.transicao_dia_noite = True
            st.rerun()