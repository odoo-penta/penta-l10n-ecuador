# Documentación Funcional — Módulo l10n_ec_account_penta (Odoo 18)

## 1. Objetivo del módulo
Este módulo extiende la contabilidad estándar de Odoo para adaptarla a prácticas contables ecuatorianas. Incorpora:
- Gestión de tarjetas (Account Cards) como un nuevo recurso.
- Personalizaciones en pagos, diarios y movimientos contables.
- Datos iniciales y configuraciones predefinidas.

**En resumen:** añade campos y opciones en pagos, movimientos y diarios, además de un nuevo modelo de tarjetas contables para un mejor control.

---

## 2. Nuevos elementos visibles en Odoo

### 2.1. Menú y vistas de Account Cards
- **Nuevo modelo:** `account.cards`.
- **Vistas añadidas:**
  - Lista (árbol) de tarjetas.
  - Formulario de tarjeta.
- **Datos precargados:** definiciones de tarjetas en `data/account_cards_data.xml`.

En la interfaz, el usuario puede crear, editar y consultar tarjetas contables asociadas a pagos u operaciones.

### 2.2. Pagos (`account.payment`)
- Se agregan campos adicionales en los pagos.
- Se personaliza el formulario de pagos para capturar información específica (relacionada con tarjetas o prácticas locales).
- Los usuarios, al registrar un pago, verán nuevos campos además de los estándar de Odoo.

### 2.3. Diarios contables (`account.journal`)
- Extiende los diarios con configuraciones adicionales.
- Los usuarios administradores contables pueden definir parámetros específicos en los diarios.

### 2.4. Movimientos contables (`account.move`)
- El formulario de asientos contables se extiende.
- Los contadores verán nuevos campos y lógica adicional al registrar apuntes.
- Conciliación de apuntes en facturas de proveedores.

---

## 3. Flujos de trabajo principales

### 3.1. Creación y uso de tarjetas contables
1. Ir al menú de Tarjetas contables (Account Cards).
2. Crear una nueva tarjeta con los datos requeridos.
3. Guardar.
4. Estas tarjetas se pueden usar en procesos de pagos o diarios según la configuración.

### 3.2. Registro de pagos
1. Ingresar a **Contabilidad → Pagos**.
2. Crear un nuevo pago.
3. Completar los campos estándar (diario, fecha, monto, partner).
4. Completar los nuevos campos añadidos por el módulo (ej: tarjeta, referencias locales).
5. Validar el pago.

➡️ El sistema registrará el pago con la información adicional exigida por normativa ecuatoriana.

### 3.3. Gestión de diarios
1. Ir a **Contabilidad → Configuración → Diarios**.
2. Al abrir un diario, se verán campos extra para configurar la integración con tarjetas o pagos locales.

### 3.4. Asientos contables
- Al crear o validar asientos, se mostrarán campos adicionales.
- El usuario contable tendrá más control sobre la información registrada.

---

## 4. Seguridad y permisos
- El archivo `security/ir.model.access.csv` habilita permisos básicos para **account.cards**.
- Esto significa que solo usuarios con perfil contable (o configurado) podrán crear/editar tarjetas.

---

## 5. Beneficios funcionales
- Cumplimiento con prácticas locales de Ecuador.
- Mayor trazabilidad de pagos y diarios.
- Gestión específica de tarjetas contables.
- Flexibilidad para configurar procesos contables adicionales.

---

## 6. Público objetivo
- **Contadores:** gestionan diarios, pagos y asientos con información extra.
- **Administradores financieros:** configuran tarjetas y diarios.
- **Usuarios de facturación/pagos:** registran pagos incluyendo la información local requerida.
