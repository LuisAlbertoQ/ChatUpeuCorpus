import React, { useEffect, useState, useCallback } from 'react';
import ChatWindow from './components/ChatWindow';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const STORAGE_SESION = 'upeu_sesion_id';
const STORAGE_PRIVACIDAD = 'upeu_privacidad_aceptada';

/** Genera o recupera un UUID persistente por navegador (T07 OE4). */
function obtenerSesionId() {
  let id = localStorage.getItem(STORAGE_SESION);
  if (!id) {
    id =
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `s_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(STORAGE_SESION, id);
  }
  return id;
}

function App() {
  const [pregunta, setPregunta] = useState('');
  const [conversacion, setConversacion] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [sesionId] = useState(obtenerSesionId);
  const [bienvenida, setBienvenida] = useState('');
  const [configPub, setConfigPub] = useState(null);
  const [restantes, setRestantes] = useState(null);
  const [privacidadAceptada, setPrivacidadAceptada] = useState(
    () => localStorage.getItem(STORAGE_PRIVACIDAD) === '1'
  );
  const [mostrarPolitica, setMostrarPolitica] = useState(false);
  const [politicaTexto, setPoliticaTexto] = useState('');

  // --- Carga inicial: M01 + configuración pública ---------------------------
  useEffect(() => {
    fetch(`${API_URL}/bienvenida`)
      .then((r) => r.json())
      .then((d) => setBienvenida(d.mensaje))
      .catch(() => setBienvenida(''));

    fetch(`${API_URL}/config-publica`)
      .then((r) => r.json())
      .then((d) => {
        setConfigPub(d);
        if (d.modo_piloto) setRestantes(d.limite_preguntas_sesion);
      })
      .catch(() => {});
  }, []);

  // --- Envío de pregunta ----------------------------------------------------
  const enviarPregunta = useCallback(async () => {
    const texto = pregunta.trim();
    if (!texto || cargando) return;
    if (!privacidadAceptada) return;

    setCargando(true);
    setConversacion((prev) => [...prev, { tipo: 'usuario', texto }]);
    setPregunta('');

    try {
      const r = await fetch(`${API_URL}/consulta`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta: texto, sesion_id: sesionId }),
      });

      if (r.status === 429) {
        const detalle = await r.json();
        const d = detalle.detail || detalle;
        setConversacion((prev) => [
          ...prev,
          {
            tipo: 'chatbot',
            respuesta: d.respuesta || 'Límite de sesión alcanzado.',
            fuentes: [],
            tipo_mensaje: 'M08',
          },
        ]);
        setRestantes(0);
        return;
      }

      const data = await r.json();
      setConversacion((prev) => [...prev, { tipo: 'chatbot', ...data }]);
      if (typeof data.preguntas_restantes === 'number') {
        setRestantes(data.preguntas_restantes);
      }
    } catch (err) {
      setConversacion((prev) => [
        ...prev,
        {
          tipo: 'chatbot',
          respuesta:
            'No se pudo contactar al servidor. Verifica tu conexión e inténtalo nuevamente.',
          fuentes: [],
          tipo_mensaje: 'M06',
        },
      ]);
    } finally {
      setCargando(false);
    }
  }, [pregunta, cargando, privacidadAceptada, sesionId]);

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviarPregunta();
    }
  };

  // --- Acciones de privacidad ----------------------------------------------
  const aceptarPrivacidad = () => {
    localStorage.setItem(STORAGE_PRIVACIDAD, '1');
    setPrivacidadAceptada(true);
  };

  const borrarHistorial = async () => {
    if (!window.confirm('¿Eliminar todas tus interacciones de esta sesión?')) return;
    try {
      await fetch(`${API_URL}/historial/${sesionId}`, { method: 'DELETE' });
      setConversacion([]);
      if (configPub?.modo_piloto) setRestantes(configPub.limite_preguntas_sesion);
    } catch {
      /* no-op */
    }
  };

  const verPolitica = async () => {
    if (politicaTexto) {
      setMostrarPolitica(true);
      return;
    }
    try {
      const r = await fetch(`${API_URL}/politica-privacidad`);
      const t = await r.text();
      setPoliticaTexto(t);
      setMostrarPolitica(true);
    } catch {
      setPoliticaTexto('No se pudo cargar la política en este momento.');
      setMostrarPolitica(true);
    }
  };

  const limiteOK = restantes === null || restantes > 0;
  const placeholder = !privacidadAceptada
    ? 'Acepta el aviso de privacidad para comenzar.'
    : !limiteOK
    ? 'Has alcanzado el límite de preguntas de esta sesión piloto.'
    : 'Escribe tu consulta sobre reglamentos, trámites o procedimientos…';

  return (
    <div className="shell">
      <div className="shell__grain" aria-hidden="true" />

      {/* ====================== HEADER ====================== */}
      <header className="head">
        <div className="head__brand">
          <span className="head__sigil">U</span>
          <div className="head__titles">
            <p className="head__eyebrow">Universidad Peruana Unión · OE5</p>
            <h1 className="head__title">
              Asistente <em>documental</em>
            </h1>
          </div>
        </div>

        <div className="head__meta">
          {configPub?.modo_piloto && (
            <span className="head__chip">
              Piloto · <strong>{restantes ?? configPub.limite_preguntas_sesion}</strong>
              /{configPub.limite_preguntas_sesion} preguntas
            </span>
          )}
          <button
            type="button"
            className="head__link"
            onClick={borrarHistorial}
            title="Eliminar mis interacciones (sección 3.4 OE4)"
          >
            Borrar mi historial
          </button>
        </div>
      </header>

      {/* ====================== MAIN ====================== */}
      <main className="main">
        <ChatWindow
          conversacion={conversacion}
          mensajeBienvenida={bienvenida}
          cargando={cargando}
        />

        <div className="composer">
          <textarea
            className="composer__input"
            value={pregunta}
            onChange={(e) => setPregunta(e.target.value)}
            onKeyDown={onKey}
            placeholder={placeholder}
            disabled={cargando || !privacidadAceptada || !limiteOK}
            rows={2}
          />
          <button
            type="button"
            className="composer__send"
            onClick={enviarPregunta}
            disabled={cargando || !privacidadAceptada || !limiteOK || !pregunta.trim()}
          >
            {cargando ? 'Consultando' : 'Preguntar'}
            <span className="composer__send-arrow">→</span>
          </button>
        </div>
      </main>

      {/* ====================== FOOTER (M07) ====================== */}
      <footer className="foot">
        <p className="foot__m07">{configPub?.mensajes?.M07 || ''}</p>
        <p className="foot__links">
          <button type="button" className="foot__link" onClick={verPolitica}>
            Política de privacidad
          </button>
          <span>·</span>
          <span className="foot__sesion">sesión {sesionId.slice(0, 8)}…</span>
        </p>
      </footer>

      {/* ====================== BANNER PRIVACIDAD ====================== */}
      {!privacidadAceptada && (
        <div className="banner" role="dialog" aria-modal="true">
          <div className="banner__card">
            <p className="banner__eyebrow">Aviso de privacidad · Ley 29733</p>
            <h2 className="banner__title">Antes de comenzar</h2>
            <p className="banner__body">
              Este sistema <strong>no solicita datos personales</strong>. Las
              interacciones se registran <strong>anonimizadas</strong> con un
              identificador de sesión generado localmente, únicamente para
              evaluación académica del proyecto. Puedes eliminar tu historial en
              cualquier momento.
            </p>
            <div className="banner__actions">
              <button type="button" className="banner__btn" onClick={verPolitica}>
                Leer política completa
              </button>
              <button
                type="button"
                className="banner__btn banner__btn--primary"
                onClick={aceptarPrivacidad}
              >
                Entiendo y acepto
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ====================== MODAL POLÍTICA ====================== */}
      {mostrarPolitica && (
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          onClick={() => setMostrarPolitica(false)}
        >
          <div className="modal__card" onClick={(e) => e.stopPropagation()}>
            <div className="modal__head">
              <p className="modal__eyebrow">Documento legal</p>
              <h2 className="modal__title">Política de privacidad</h2>
              <button
                type="button"
                className="modal__close"
                onClick={() => setMostrarPolitica(false)}
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>
            <pre className="modal__body">{politicaTexto}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
