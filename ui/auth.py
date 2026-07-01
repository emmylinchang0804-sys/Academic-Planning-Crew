"""Streamlit login and registration screens."""

import streamlit as st

from academic_planning.auth import UserRegistry, login_session, logout_session
from ui.shared import (
    AUTH_DISPLAY_MODES,
    apply_sample_data,
    default_store,
    display_mode,
    initialize_store_theme_from_session,
    save_store,
    session_display_mode,
    set_session_display_mode,
)


def password_input(label, key, help_text=None):
    return st.text_input(
        label,
        type="password",
        key=key,
        help=help_text,
    )


def render_auth_screen(registry_path):
    st.markdown(
        '<div class="app-title">Academic Planning Crew</div>',
        unsafe_allow_html=True,
    )
    st.caption("Tu planificación académica, ahora en un espacio personal.")
    if st.session_state.pop("account_deleted", False):
        st.success("Cuenta eliminada. Puedes iniciar sesión o crear una cuenta nueva.")

    selected_mode = st.segmented_control(
        "Tema",
        AUTH_DISPLAY_MODES,
        default=session_display_mode(),
        key="auth_display_mode_selector",
    )
    if selected_mode and selected_mode != session_display_mode():
        set_session_display_mode(selected_mode)
        st.rerun()

    login_tab, register_tab = st.tabs(["Iniciar sesión", "Crear cuenta"])
    registry = UserRegistry(registry_path)

    with login_tab:
        email = st.text_input("Correo electrónico", key="login_email")
        password = password_input("Contraseña", "login_password")
        if st.button("Iniciar sesión", width="stretch", key="login_submit"):
            user = registry.authenticate(email, password)
            if user:
                login_session(st.session_state, user)
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")

    with register_tab:
        display_name = st.text_input("Nombre", key="register_name")
        email = st.text_input("Correo electrónico", key="register_email")
        password = password_input(
            "Contraseña (mínimo 8 caracteres)",
            "register_password",
        )
        confirmation = password_input(
            "Confirmar contraseña",
            "register_confirmation",
        )
        use_sample_data = st.radio(
            "¿Deseas comenzar con datos de demostración?",
            ["Sí", "No"],
            horizontal=True,
            index=1,
            key="register_sample_data",
        )
        if st.button("Crear cuenta", width="stretch", key="register_submit"):
            if password != confirmation:
                st.error("Las contraseñas no coinciden.")
            else:
                user, error = registry.register(email, password, display_name)
                if error:
                    st.error(error)
                else:
                    store = default_store()
                    initialize_store_theme_from_session(store)
                    if use_sample_data == "Sí":
                        apply_sample_data(store)
                    save_store(store, user["user_id"])
                    login_session(st.session_state, user)
                    st.session_state["registration_completed"] = True
                    st.success("Cuenta creada.")
                    st.rerun()


def render_user_sidebar(user):
    with st.sidebar:
        st.caption("Sesión activa")
        st.write(f"**{user.get('display_name', 'Usuario')}**")
        st.caption(user.get("email", ""))
        if st.button("Cerrar sesión", width="stretch"):
            preferred_mode = display_mode(st.session_state.get("_app_store", {}))
            if preferred_mode not in AUTH_DISPLAY_MODES:
                preferred_mode = session_display_mode()
            logout_session(st.session_state)
            set_session_display_mode(preferred_mode)
            st.session_state.pop("pending_display_mode", None)
            st.rerun()
