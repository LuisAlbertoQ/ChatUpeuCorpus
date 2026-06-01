# Política de Privacidad – Chatbot UPeU

**Versión 1.0 — Junio 2025**
**Marco legal:** Ley N.° 29733, Ley de Protección de Datos Personales del Perú y su Reglamento (D.S. N.° 003-2013-JUS).
**Documento de alcance:** OE4 v2.0 (sección 3).

---

## 1. ¿Quién es responsable del tratamiento?

El presente sistema es operado por el equipo de investigación de la **Escuela Profesional de Ingeniería de Sistemas — Universidad Peruana Unión (UPeU)**, en el marco del Proyecto de Investigación de Pregrado (PPI):

> *Sistema conversacional universitario con IA generativa explicable y trazabilidad documental.*

Equipo responsable:
- David Robert Yucra Mamani
- Luis Alberto Quilla López
- Gladys Rosaura Yana Pari
- Asesor: Mg. Esteban Tocto Cano

---

## 2. Datos que NO solicitamos

El sistema **no solicita** ni requiere ninguno de los siguientes datos para funcionar:

- Nombres, apellidos, DNI ni código de estudiante.
- Correo electrónico, teléfono ni dirección.
- Datos biométricos, financieros o de salud.
- Credenciales de acceso a sistemas institucionales.

---

## 3. Datos que se procesan (uso temporal)

Para responder a tu consulta y mejorar el sistema (OE6/OE8), se procesa de forma **anonimizada y mínima**:

| Dato | Propósito | Retención |
|---|---|---|
| Texto de la pregunta | Recuperación de fragmentos + generación de respuesta | Tiempo de la sesión |
| Identificador de sesión (UUID generado por tu navegador) | Agrupar interacciones de una misma sesión piloto (T07) | Hasta que solicites su eliminación o termine el proyecto |
| Respuesta generada | Evaluación de cobertura, precisión y trazabilidad | Idem |
| Fuentes documentales recuperadas | Trazabilidad y explicabilidad | Idem |
| Marca temporal (timestamp) | Medición de tiempos de respuesta y volumen | Idem |
| Tipo de mensaje (M02/M03/…/M07) | Métricas de comportamiento del sistema | Idem |

**Antes de almacenarse**, la pregunta y la respuesta pasan por un filtro automático que sustituye con etiquetas (`[DNI]`, `[EMAIL]`, `[TEL]`, `[COD_EST]`) cualquier identificador que el usuario haya tipeado voluntariamente.

---

## 4. ¿Quién accede a los datos?

- Únicamente el equipo de investigación, con fines exclusivamente académicos.
- **No se comparten con terceros.**
- **No se realiza transferencia internacional** de datos.
- **No se utilizan para perfilado comercial** ni para decisiones automatizadas con efectos jurídicos.

---

## 5. Tus derechos (Ley 29733)

Tienes derecho a:

1. **Acceder** a las interacciones registradas con tu identificador de sesión.
2. **Rectificar** datos inexactos (en este sistema no hay datos identificables, pero el derecho aplica).
3. **Eliminar (derecho al olvido)** todas las interacciones de tu sesión.
   - Endpoint: `DELETE /historial/{sesion_id}` o usando el botón **“Borrar mi historial”** del frontend.
4. **Oponerte** al tratamiento dejando de usar el sistema en cualquier momento.

---

## 6. Seguridad

- Los datos se almacenan en una base SQLite local del servidor, no expuesta directamente a Internet.
- No se utiliza el servicio para almacenar credenciales ni datos sensibles.
- Las consultas viajan por HTTP/HTTPS según el despliegue (en producción se exige HTTPS).

---

## 7. Limitaciones del sistema (transparencia)

- Las respuestas son generadas por **inteligencia artificial** y se basan únicamente en el corpus documental oficial vectorizado.
- El sistema es **informativo**: no reemplaza decisiones administrativas oficiales.
- Verifica siempre con la oficina o documento original cuando el trámite sea formal.

---

## 8. Vigencia y contacto

Esta política rige mientras el sistema esté en operación piloto. Al finalizar el proyecto, los registros se destruirán salvo aquellos requeridos por la sustentación académica, los cuales se conservarán anonimizados.

Cualquier consulta relativa a esta política puede dirigirse al equipo de investigación o al asesor académico responsable.

---

*Última actualización: junio de 2025*
