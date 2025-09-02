import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import datetime

import os
import requests
import socketio
import threading

import shutil
import sys
# Comprobar si la librería de imágenes (Pillow) está disponible
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Paleta de colores actualizada, más suave y moderna
COLOR_PALETTE = {
    "background": "#F0F0F0",
    "surface": "#FFFFFF",
    "primary": "#607D8B",
    "accent": "#90A4AE",
    "text_dark": "#263238",
    "text_light": "#ECEFF1",
    "row_entrada": "#E8F5E9",  # Verde claro para entradas
    "row_salida": "#FFEBEE",   # Rosa claro para salidas
}

class AutocompleteEntry(ttk.Entry):
    """
    Un widget de entrada con autocompletado, lista desplegable y navegación por teclado.
    """

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.lista_sugerencias = []
        self.listbox = None
        self.autocompletado_id = None
        self.bind("<KeyRelease>", self.on_keyrelease)
        self.bind("<FocusOut>", self.on_focusout)
        self.bind("<Return>", self.seleccionar_con_enter)
        self.bind("<Escape>", self.cerrar_listbox)
        self.bind("<Down>", self.mostrar_sugerencias_al_pulsar_abajo)

    def set_sugerencias(self, suggestions):
        self.lista_sugerencias = sorted(suggestions)

    def on_keyrelease(self, event):
        """Maneja las pulsaciones de teclas para autocompletar y navegar."""
        # Las teclas de navegación y escape se gestionan en sus propios bindings
        # o aquí para evitar que se dispare el autocompletado.
        if event.keysym == 'Down':
            self.navegar_listbox(1)
            return
        elif event.keysym == 'Up':
            self.navegar_listbox(-1)
            return
        elif event.keysym in ('Return', 'Escape'):
            # Estos tienen sus propios bindings, no hacemos nada más aquí.
            return

        # Para cualquier otra tecla, disparamos el autocompletado y el evento de cambio de texto
        if self.autocompletado_id:
            self.after_cancel(self.autocompletado_id)
        
        # Dispara el evento para el filtrado en tiempo real en la app principal
        self.event_generate("<<TextChanged>>")
        # Programa el autocompletado después de una breve pausa
        self.autocompletado_id = self.after(300, self.realizar_autocompletado)

    def mostrar_sugerencias_al_pulsar_abajo(self, event):
        """Muestra todas las sugerencias si se pulsa la tecla Abajo y el campo está vacío."""
        if not self.get() and not self.listbox:
            self.mostrar_listbox(self.lista_sugerencias)
        else:
            self.navegar_listbox(1)

    def realizar_autocompletado(self, event=None):
        """Realiza la búsqueda de sugerencias y muestra el listbox."""
        termino = self.get().lower()
        if not termino:
            self.cerrar_listbox()
            return

        coincidencias = [item for item in self.lista_sugerencias if termino in item.lower()]

        if coincidencias:
            self.mostrar_listbox(coincidencias)
        else:
            self.cerrar_listbox()

    def mostrar_listbox(self, items):
        """Crea y muestra el widget de listbox con sugerencias, ajustando su tamaño."""
        self.cerrar_listbox()

        self.listbox = tk.Toplevel(self.master)
        self.listbox.overrideredirect(True)

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.listbox.geometry(f"+{x}+{y}")

        listbox_frame = tk.Frame(self.listbox, bd=1, relief="solid")
        listbox_frame.pack(fill="both", expand=True)

        # --- CÁLCULO DEL ANCHO ---
        # Calcular el ancho en caracteres basado en el ítem más largo para que se vea completo.
        max_len = 0
        if items:
            max_len = max(len(s) for s in items)

        # El ancho del Entry en píxeles, convertido a un ancho aproximado en caracteres.
        # Esta es una heurística; 7 es un buen divisor para fuentes de UI comunes.
        entry_width_chars = self.winfo_width() // 7
        
        # El ancho del listbox será el mayor entre el texto más largo y el ancho del entry.
        # Se añade un padding y se limita el ancho máximo para evitar que sea excesivo.
        new_width = min(max(max_len, entry_width_chars) + 2, 100)

        # Ajustar la altura del listbox a la cantidad de elementos, con un máximo para no saturar
        altura_listbox = min(len(items), 10)
        listbox_widget = tk.Listbox(listbox_frame, background=COLOR_PALETTE["surface"], relief="flat", height=altura_listbox, width=new_width)
        for item in items:
            listbox_widget.insert("end", item)

        listbox_widget.pack(fill="both", expand=True)
        listbox_widget.bind("<<ListboxSelect>>", self.on_listbox_select)
        listbox_widget.bind("<ButtonRelease-1>", self.on_listbox_select)
        # Se ha quitado el binding de Return aquí, se maneja directamente en la clase principal
        self.listbox_widget = listbox_widget

    def on_listbox_select(self, event):
        """Maneja la selección de un ítem en el listbox."""
        seleccion = event.widget.curselection()
        if seleccion:
            valor = event.widget.get(seleccion[0])
            self.delete(0, "end")
            self.insert(0, valor)
            self.cerrar_listbox()
            self.event_generate("<<SelectionMade>>")

    def seleccionar_con_enter(self, event=None):
        """
        Selecciona el ítem resaltado en la lista con la tecla Enter y luego
        genera el evento para pasar al siguiente campo.
        """
        if self.listbox and self.listbox_widget:
            indices_seleccionados = self.listbox_widget.curselection()
            if indices_seleccionados:
                index = indices_seleccionados[0]
                valor = self.listbox_widget.get(index)
                self.delete(0, "end")
                self.insert(0, valor)
            self.cerrar_listbox()
        self.event_generate("<<FocusNext>>")

    def navegar_listbox(self, direccion):
        """Navega por la lista de sugerencias con las flechas del teclado."""
        if not self.listbox or not self.listbox_widget:
            return

        current_selection = self.listbox_widget.curselection()

        if not current_selection:
            new_index = 0 if direccion == 1 else self.listbox_widget.size() - 1
            self.listbox_widget.selection_set(new_index)
            self.listbox_widget.activate(new_index)
            self.listbox_widget.see(new_index)
            return

        index = current_selection[0]
        new_index = index + direccion

        if 0 <= new_index < self.listbox_widget.size():
            self.listbox_widget.selection_clear(0, 'end')
            self.listbox_widget.selection_set(new_index)
            self.listbox_widget.activate(new_index)
            self.listbox_widget.see(new_index)

    def on_focusout(self, event):
        """Cierra el listbox cuando se pierde el foco."""
        self.after(200, self.cerrar_listbox)

    def cerrar_listbox(self, event=None):
        """Destruye el widget de listbox si está abierto."""
        if self.listbox:
            self.listbox.destroy()
            self.listbox = None
            self.listbox_widget = None
            if self.autocompletado_id:
                self.after_cancel(self.autocompletado_id)
                self.autocompletado_id = None


class InventarioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestión de Inventario")
        self.root.state('zoomed')

        # --- CONFIGURACIÓN DE RUTAS PARA PORTABILIDAD ---
        # Determina la ruta base para que funcione tanto en desarrollo como en el ejecutable
        if getattr(sys, 'frozen', False):
            # Si la aplicación está 'congelada' (ejecutable)
            self.base_path = os.path.dirname(sys.executable)
        else:
            # Si se está ejecutando como un script normal
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        # Define la ruta de la base de datos y la carpeta de imágenes
        self.image_dir = os.path.join(self.base_path, "imagenes_materiales")
        os.makedirs(self.image_dir, exist_ok=True) # Crea la carpeta si no existe

        # --- CONFIGURACIÓN CLIENTE-SERVIDOR ---
        # Apunta a nuestro servidor en la nube, que está siempre activo.
        self.server_url = "https://inventario-server-zlvy.onrender.com"
        self.sio = socketio.Client()
        self.setup_socketio_handlers()

        # Listas para autocompletado (se cargarán desde el servidor)
        self.nombres_proveedores = []
        self.nombres_destinos = []

        # --- ESTADO PARA LA INTERFAZ ---
        self.filtros_activos = {} # Para los filtros de columna en el historial

        self.configurar_gui()
        self.conectar_al_servidor()

    def conectar_al_servidor(self):
        """Intenta conectar con el servidor Socket.IO en un hilo separado."""
        def run():
            try:
                self.sio.connect(self.server_url)
                # Una vez conectado, carga los datos iniciales
                self.root.after(0, self.recargar_todo)
            except socketio.exceptions.ConnectionError as e:
                self.root.after(0, lambda: self.mostrar_notificacion(f"Error de conexión: No se pudo conectar al servidor en {self.server_url}", "error"))
        
        threading.Thread(target=run, daemon=True).start()

    def setup_socketio_handlers(self):
        """Define qué hacer cuando el servidor envía eventos."""
        @self.sio.on('connect')
        def on_connect():
            print("Conectado al servidor!")

        @self.sio.on('actualizacion_servidor')
        def on_server_update(data):
            print(f"Recibida actualización del servidor: {data}")
            # El servidor nos dice que algo cambió, así que recargamos las vistas.
            # Usamos `root.after` para asegurar que la actualización de GUI se ejecute en el hilo principal.
            self.root.after(0, self.recargar_todo)

        @self.sio.on('disconnect')
        def on_disconnect():
            print("Desconectado del servidor.")
            self.root.after(0, lambda: self.mostrar_notificacion("Desconectado del servidor.", "error"))

    def recargar_todo(self):
        """Función central para recargar todos los datos y vistas desde el servidor."""
        self.mostrar_inventario_gui()
        self.mostrar_historial_gui()
        # self.mostrar_materiales_gui() # Descomentar cuando implementes la API de materiales
        # self._recargar_datos_y_sugerencias() # Descomentar cuando implementes la API de sugerencias


    def configurar_gui(self):
        """
        Configura la estructura principal de la interfaz gráfica.
        """
        self.root.configure(bg=COLOR_PALETTE["background"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=COLOR_PALETTE["background"])
        style.configure("TFrame", background=COLOR_PALETTE["background"])
        style.configure("TLabel", background=COLOR_PALETTE["background"], foreground=COLOR_PALETTE["text_dark"])
        style.configure("TButton", background=COLOR_PALETTE["primary"], foreground=COLOR_PALETTE["text_light"])
        style.map("TButton", background=[('active', COLOR_PALETTE["accent"])])
        style.configure("Treeview", background=COLOR_PALETTE["surface"], foreground=COLOR_PALETTE["text_dark"], fieldbackground=COLOR_PALETTE["surface"])
        style.map("Treeview", background=[('selected', COLOR_PALETTE["accent"])])

        self.notificacion_frame = tk.Frame(self.root, bg=COLOR_PALETTE["background"])
        self.notificacion_frame.pack(side="bottom", padx=10, pady=10, anchor="e")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.inventario_tab = ttk.Frame(self.notebook, style="TFrame")
        self.historial_tab = ttk.Frame(self.notebook, style="TFrame")
        self.materiales_tab = ttk.Frame(self.notebook, style="TFrame")

        self.notebook.add(self.inventario_tab, text="Inventario")
        self.notebook.add(self.historial_tab, text="Historial")
        self.notebook.add(self.materiales_tab, text="Materiales")

        self.configurar_inventario_tab()
        self.configurar_historial_tab()
        self.configurar_materiales_tab()

    def configurar_inventario_tab(self):
        """
        Configura la interfaz de la pestaña de Inventario con la barra de búsqueda y filtro.
        """
        top_frame = ttk.Frame(self.inventario_tab)
        top_frame.pack(fill="x", pady=10, padx=10)

        # Barra de búsqueda con autocompletado
        ttk.Label(top_frame, text="Buscar Artículo:").pack(side="left", padx=(0, 5))
        self.busqueda_inventario_entry = AutocompleteEntry(top_frame)
        self.busqueda_inventario_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.busqueda_inventario_entry.bind("<<SelectionMade>>", self.filtrar_inventario)
        self.busqueda_inventario_entry.bind("<<TextChanged>>", self.filtrar_inventario)

        # Botones de gestión
        ttk.Button(top_frame, text="Agregar Artículo", command=self.agregar_articulo_gui).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Eliminar Artículo", command=self.eliminar_articulo_gui).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Importar", command=self.importar_inventario).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Exportar", command=self.exportar_inventario).pack(side="right", padx=5)

        # Treeview para mostrar el inventario
        # Frame para contener el Treeview y la Scrollbar
        tree_frame = ttk.Frame(self.inventario_tab)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Se ha eliminado la columna de "Proveedor" a petición del usuario.
        self.tree_inventario = ttk.Treeview(tree_frame, columns=("Nombre", "Cantidad", "Unidad"), show="headings")
        self.tree_inventario.heading("Nombre", text="Nombre")
        self.tree_inventario.heading("Cantidad", text="Cantidad")
        self.tree_inventario.heading("Unidad", text="Unidad")

        self.tree_inventario.column("Nombre", stretch=tk.YES)
        self.tree_inventario.column("Cantidad", width=100, stretch=tk.NO)
        self.tree_inventario.column("Unidad", width=100, stretch=tk.NO)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_inventario.yview)
        self.tree_inventario.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree_inventario.pack(side="left", fill="both", expand=True)

        # Código para el menú contextual del inventario
        self.menu_contextual = tk.Menu(self.root, tearoff=0)
        self.menu_contextual.add_command(label="Editar Artículo", command=self.editar_articulo_gui)
        self.menu_contextual.add_command(label="Eliminar Artículo", command=self.eliminar_articulo_gui)
        self.tree_inventario.bind("<Button-3>", self.mostrar_menu_contextual)

        self.mostrar_inventario_gui()

    def mostrar_menu_contextual(self, event):
        """
        Muestra el menú contextual al hacer clic derecho en un ítem de la tabla del inventario.
        """
        item_id = self.tree_inventario.identify_row(event.y)
        if item_id:
            self.tree_inventario.selection_set(item_id)
            try:
                self.menu_contextual.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu_contextual.grab_release()

    def editar_articulo_gui(self):
        """
        Abre una ventana de diálogo para editar el artículo seleccionado.
        """
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione un artículo para editar.", "error")
            return

        item = self.tree_inventario.item(seleccion[0])
        nombre_actual = item['values'][0]

        # NOTA: La edición es compleja en un entorno multiusuario.
        # Por simplicidad, esta función se deja como ejercicio.
        # Requeriría una API en el servidor (ej. PUT /articulo/<id>)
        self.mostrar_notificacion("La función de editar aún no está implementada para el modo servidor.", "info")

        ventana_edicion = tk.Toplevel(self.root)
        ventana_edicion.title("Editar Artículo")
        ventana_edicion.transient(self.root)
        ventana_edicion.grab_set()

        frame_edicion = ttk.Frame(ventana_edicion, padding="10")
        frame_edicion.pack()

        ttk.Label(frame_edicion, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5)
        nombre_entry = ttk.Entry(frame_edicion)
        nombre_entry.insert(0, nombre_actual)
        nombre_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame_edicion, text="Cantidad:").grid(row=1, column=0, sticky="w", pady=5)
        cantidad_entry = ttk.Entry(frame_edicion)
        cantidad_entry.insert(0, item['values'][1])
        cantidad_entry.grid(row=1, column=1, pady=5)

        ttk.Label(frame_edicion, text="Proveedor:").grid(row=2, column=0, sticky="w", pady=5)
        proveedor_entry = AutocompleteEntry(frame_edicion)
        # Se establece la lista de autocompletado para el campo de proveedor
        proveedor_entry.set_sugerencias(self.nombres_proveedores)
        # proveedor_entry.insert(0, proveedor_db) # Necesitarías obtener esto del servidor
        proveedor_entry.grid(row=2, column=1, pady=5)

        def guardar_cambios():
            nuevo_nombre = nombre_entry.get().strip().upper()  # Convertir a mayúsculas
            nueva_cantidad_str = cantidad_entry.get().strip()
            nuevo_proveedor = proveedor_entry.get().strip().upper()  # Convertir a mayúsculas

            if not nuevo_nombre or not nueva_cantidad_str:
                self.mostrar_notificacion("Los campos 'Nombre' y 'Cantidad' son obligatorios.", "error")
                return

            try:
                nueva_cantidad = int(nueva_cantidad_str)
                if nueva_cantidad < 0:
                    raise ValueError
            except ValueError:
                self.mostrar_notificacion("La cantidad debe ser un número entero no negativo.", "error")
                return

            # Aquí iría la llamada a la API del servidor para actualizar

        ttk.Button(frame_edicion, text="Guardar Cambios", command=guardar_cambios).grid(row=3, column=0, columnspan=2, pady=10)

    def agregar_articulo_gui(self):
        """
        Abre una ventana de diálogo para agregar un nuevo artículo.
        """
        ventana_agregar = tk.Toplevel(self.root)
        ventana_agregar.title("Agregar Nuevo Artículo")
        ventana_agregar.transient(self.root)
        ventana_agregar.grab_set()

        frame_agregar = ttk.Frame(ventana_agregar, padding="10")
        frame_agregar.pack()

        ttk.Label(frame_agregar, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5)
        nombre_entry = ttk.Entry(frame_agregar)
        nombre_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame_agregar, text="Cantidad Inicial:").grid(row=1, column=0, sticky="w", pady=5)
        cantidad_entry = ttk.Entry(frame_agregar)
        cantidad_entry.grid(row=1, column=1, pady=5)

        ttk.Label(frame_agregar, text="Proveedor:").grid(row=2, column=0, sticky="w", pady=5)
        proveedor_entry = AutocompleteEntry(frame_agregar)
        # Se establece la lista de autocompletado para el campo de proveedor
        proveedor_entry.set_sugerencias(self.nombres_proveedores)
        proveedor_entry.grid(row=2, column=1, pady=5)

        def guardar_articulo():
            nombre = nombre_entry.get().strip().upper()  # Convertir a mayúsculas
            cantidad_str = cantidad_entry.get().strip()
            proveedor = proveedor_entry.get().strip().upper()  # Convertir a mayúsculas

            if not nombre or not cantidad_str:
                self.mostrar_notificacion("Los campos 'Nombre' y 'Cantidad' son obligatorios.", "error")
                return

            try:
                cantidad = int(cantidad_str)
                if cantidad < 0:
                    raise ValueError
            except ValueError:
                self.mostrar_notificacion("La cantidad debe ser un número entero no negativo.", "error")
                return

            # NOTA: La adición de artículos debería ser a través de una entrada inicial.
            # Si se desea agregar artículos vacíos, se necesitaría una API específica.
            self.mostrar_notificacion("Para agregar un artículo, registre una 'Entrada' en la pestaña Historial.", "info")
            ventana_agregar.destroy()

        ttk.Button(frame_agregar, text="Guardar", command=guardar_articulo).grid(row=3, column=0, columnspan=2, pady=10)

    def eliminar_articulo_gui(self):
        """
        Elimina un artículo seleccionado de la base de datos y la 
        GUI.
        """
        seleccion = self.tree_inventario.selection()
        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione un artículo para eliminar.", "error")
            return

        item = self.tree_inventario.item(seleccion[0])
        nombre_articulo = item['values'][0]

        if messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar '{nombre_articulo}'?"):
            # NOTA: La eliminación es compleja. ¿Qué pasa con su historial?
            # Por simplicidad, se deja como ejercicio. Requeriría una API (ej. DELETE /articulo/<id>)
            self.mostrar_notificacion("La función de eliminar aún no está implementada para el modo servidor.", "info")

    def mostrar_inventario_gui(self):
        """
        Actualiza y muestra la lista de artículos en el Treeview del inventario.
        """
        for item in self.tree_inventario.get_children():
            self.tree_inventario.delete(item)

        try:
            response = requests.get(f"{self.server_url}/inventario")
            response.raise_for_status()  # Lanza una excepción para códigos de error HTTP
            inventario = response.json() # Espera una lista de diccionarios

            for item in inventario:
                # Adaptar los datos recibidos a las columnas del Treeview
                # El servidor ahora nos da la unidad de medida directamente
                values = (item['nombre'], item['cantidad'], item['unidad_medicion'])
                self.tree_inventario.insert('', 'end', values=values)

        except requests.exceptions.RequestException as e:
            self.mostrar_notificacion(f"Error al conectar con el servidor: {e}", "error")
        except Exception as e:
            self.mostrar_notificacion(f"Error al procesar la respuesta del servidor: {e}", "error")

    def filtrar_inventario(self, event=None):
        """
        Filtra el Treeview del inventario basándose en el término de búsqueda.
        """
        termino_busqueda = self.busqueda_inventario_entry.get().lower().strip()
        # NOTA: El filtrado ahora debería hacerse en el lado del cliente sobre los datos ya cargados,
        # o el servidor debería proporcionar un endpoint de búsqueda (ej. /inventario?q=termino)
        self.mostrar_inventario_gui() # Por ahora, solo recargamos todo
        self.mostrar_notificacion("El filtrado en vivo aún no está implementado para el modo servidor.", "info")

    def importar_inventario(self):
        """Importa datos de artículos desde un archivo Excel."""
        filepath = filedialog.askopenfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        if not filepath:
            return

        # NOTA: La importación masiva requeriría una API específica en el servidor.
        self.mostrar_notificacion("La importación masiva debe hacerse a través de la API del servidor.", "info")

    def exportar_inventario(self):
        """Exporta los datos del inventario a un archivo Excel."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not filepath:
            return

        try:
            response = requests.get(f"{self.server_url}/inventario")
            response.raise_for_status()
            df = pd.DataFrame(response.json())
            df.to_excel(filepath, index=False, header=["Nombre", "Cantidad", "Unidad"])
            self.mostrar_notificacion(f"Inventario exportado a: {filepath}", "exito")
        except Exception as e:
            self.mostrar_notificacion(f"Error al exportar el inventario: {e}", "error")

    def configurar_materiales_tab(self):
        """
        Configura la interfaz de la pestaña de Materiales.
        """
        top_frame = ttk.Frame(self.materiales_tab)
        top_frame.pack(fill="x", pady=10, padx=10)

        # Barra de búsqueda con autocompletado para materiales
        ttk.Label(top_frame, text="Buscar Material:").pack(side="left", padx=(0, 5))
        self.busqueda_materiales_entry = AutocompleteEntry(top_frame)
        self.busqueda_materiales_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.busqueda_materiales_entry.bind("<<SelectionMade>>", self.filtrar_materiales)
        self.busqueda_materiales_entry.bind("<<TextChanged>>", self.filtrar_materiales)

        # Botones de gestión para materiales
        ttk.Button(top_frame, text="Agregar Material", command=self.agregar_material_gui).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Eliminar Material", command=self.eliminar_material_gui).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Importar", command=self.importar_materiales).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Exportar", command=self.exportar_materiales).pack(side="right", padx=5)

        # Treeview para mostrar los materiales
        # Frame para contener el Treeview y la Scrollbar
        tree_frame_mat = ttk.Frame(self.materiales_tab)
        tree_frame_mat.pack(fill="both", expand=True, padx=10, pady=10)

        # Se elimina la columna de ID
        self.tree_materiales = ttk.Treeview(tree_frame_mat, columns=("Imagen", "Nombre", "Unidad"), show="headings")
        self.tree_materiales.heading("Imagen", text="Img")
        self.tree_materiales.heading("Nombre", text="Nombre del Material")
        self.tree_materiales.heading("Unidad", text="Unidad de Medición")

        self.tree_materiales.column("Imagen", width=40, stretch=tk.NO, anchor="center")
        self.tree_materiales.column("Nombre", stretch=tk.YES)
        self.tree_materiales.column("Unidad", width=150, stretch=tk.NO)
        
        # Tag para colorear el indicador de imagen
        self.tree_materiales.tag_configure('con_imagen', foreground='green')

        scrollbar_mat = ttk.Scrollbar(tree_frame_mat, orient="vertical", command=self.tree_materiales.yview)
        self.tree_materiales.configure(yscrollcommand=scrollbar_mat.set)
        scrollbar_mat.pack(side="right", fill="y")
        self.tree_materiales.pack(side="left", fill="both", expand=True)

        # Código para el menú contextual de materiales
        self.menu_contextual_materiales = tk.Menu(self.root, tearoff=0)
        self.menu_contextual_materiales.add_command(label="Agregar/Cambiar Imagen", command=self.agregar_imagen_material_gui)
        self.menu_contextual_materiales.add_command(label="Editar Material", command=self.editar_material_gui)
        self.menu_contextual_materiales.add_command(label="Eliminar Material", command=self.eliminar_material_gui)
        self.tree_materiales.bind("<Button-3>", self.mostrar_menu_contextual_materiales)
        self.tree_materiales.bind("<Double-1>", self.visualizar_imagen_material)

        self.mostrar_materiales_gui()

    def mostrar_menu_contextual_materiales(self, event):
        """
        Muestra el menú contextual al hacer clic derecho en un ítem de la tabla de materiales.
        """
        item_id = self.tree_materiales.identify_row(event.y)
        if item_id:
            self.tree_materiales.selection_set(item_id)
            try:
                self.menu_contextual_materiales.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu_contextual_materiales.grab_release()

    def filtrar_materiales(self, event=None):
        """
        Filtra el Treeview de materiales basándose en el término de búsqueda.
        """
        termino_busqueda = self.busqueda_materiales_entry.get().lower().strip()

        if not termino_busqueda:
            self.mostrar_materiales_gui()
            return
        
        self.mostrar_notificacion("El filtrado de materiales no está implementado para el modo servidor.", "info")

    def mostrar_materiales_gui(self):
        """
        Actualiza y muestra la lista de materiales predefinidos en el Treeview.
        """
        for item in self.tree_materiales.get_children():
            self.tree_materiales.delete(item)

        # NOTA: Implementar API GET /materiales en el servidor
        self.mostrar_notificacion("La carga de materiales no está implementada para el modo servidor.", "info")

    def agregar_material_gui(self):
        """
        Abre una ventana de diálogo para agregar un nuevo material.
        """
        ventana_agregar = tk.Toplevel(self.root)
        ventana_agregar.title("Agregar Nuevo Material")
        ventana_agregar.transient(self.root)
        ventana_agregar.grab_set()

        frame_agregar = ttk.Frame(ventana_agregar, padding="10")
        frame_agregar.pack()

        ttk.Label(frame_agregar, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5)
        nombre_entry = ttk.Entry(frame_agregar)
        nombre_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame_agregar, text="Unidad de Medición:").grid(row=1, column=0, sticky="w", pady=5)
        unidad_entry = ttk.Entry(frame_agregar)
        unidad_entry.grid(row=1, column=1, pady=5)

        def guardar_material():
            nombre = nombre_entry.get().strip().upper()  # Convertir a mayúsculas
            unidad = unidad_entry.get().strip().upper()  # Convertir a mayúsculas

            if not nombre:
                self.mostrar_notificacion("El campo 'Nombre del Material' es obligatorio.", "error")
                return

            # NOTA: Implementar API POST /material en el servidor
            self.mostrar_notificacion("La adición de materiales no está implementada para el modo servidor.", "info")

        ttk.Button(frame_agregar, text="Guardar", command=guardar_material).grid(row=2, column=0, columnspan=2, pady=10)

    def editar_material_gui(self):
        """
        Abre una ventana de diálogo para editar el material seleccionado.
        """
        seleccion = self.tree_materiales.selection()
        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione un material para editar.", "error")
            return

        item = self.tree_materiales.item(seleccion[0])
        nombre_actual = item['values'][1]

        # NOTA: Implementar API PUT /material/<id> en el servidor
        self.mostrar_notificacion("La edición de materiales no está implementada para el modo servidor.", "info")
        ventana_edicion = tk.Toplevel(self.root)
        ventana_edicion.title("Editar Material")
        ventana_edicion.transient(self.root)
        ventana_edicion.grab_set()

        frame_edicion = ttk.Frame(ventana_edicion, padding="10")
        frame_edicion.pack()

        ttk.Label(frame_edicion, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5)
        nombre_entry = ttk.Entry(frame_edicion)
        nombre_entry.insert(0, nombre_actual)
        nombre_entry.grid(row=0, column=1, pady=5)

        ttk.Label(frame_edicion, text="Unidad de Medición:").grid(row=1, column=0, sticky="w", pady=5)
        unidad_entry = ttk.Entry(frame_edicion)
        # unidad_entry.insert(0, unidad_db)
        unidad_entry.grid(row=1, column=1, pady=5)

        def guardar_cambios():
            nuevo_nombre = nombre_entry.get().strip().upper()  # Convertir a mayúsculas
            nueva_unidad = unidad_entry.get().strip().upper()  # Convertir a mayúsculas

            if not nuevo_nombre:
                self.mostrar_notificacion("El campo 'Nombre' es obligatorio.", "error")
                return

            # Aquí iría la llamada a la API del servidor
        ttk.Button(frame_edicion, text="Guardar Cambios", command=guardar_cambios).grid(row=2, column=0, columnspan=2, pady=10)

    def eliminar_material_gui(self):
        """
        Elimina un material seleccionado de la base de datos y la 
        GUI.
        """
        seleccion = self.tree_materiales.selection()
        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione un material para eliminar.", "error")
            return

        item = self.tree_materiales.item(seleccion[0])
        nombre_material = item['values'][1]

        if messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar '{nombre_material}'?"):
            # NOTA: Implementar API DELETE /material/<id> en el servidor
            self.mostrar_notificacion("La eliminación de materiales no está implementada para el modo servidor.", "info")

    def importar_materiales(self):
        """Importa datos de materiales desde un archivo Excel."""
        filepath = filedialog.askopenfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        if not filepath:
            return

        # NOTA: Implementar API POST /materiales/importar en el servidor
        self.mostrar_notificacion("La importación de materiales no está implementada para el modo servidor.", "info")

    def exportar_materiales(self):
        """Exporta los datos de los materiales a un archivo Excel."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not filepath:
            return

        try:
            # NOTA: Implementar API GET /materiales en el servidor
            self.mostrar_notificacion(f"Materiales exportados a: {filepath}", "exito")
        except Exception as e:
            self.mostrar_notificacion(f"Error al exportar los materiales: {e}", "error")

    def agregar_imagen_material_gui(self):
        """
        Abre un diálogo para seleccionar una imagen y asociarla a un material.
        """
        seleccion = self.tree_materiales.selection()
        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione un material.", "error")
            return

        item = self.tree_materiales.item(seleccion[0])
        nombre_material = item['values'][1]

        filepath = filedialog.askopenfilename(
            title="Seleccionar imagen para el material",
            filetypes=[("Archivos de Imagen", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Todos los archivos", "*.*")]
        )

        if not filepath:
            return

        # NOTA: Implementar API POST /material/<id>/imagen en el servidor
        self.mostrar_notificacion("La carga de imágenes no está implementada para el modo servidor.", "info")

    def visualizar_imagen_material(self, event):
        """
        Muestra la imagen asociada a un material al hacer doble clic.
        """
        if not PIL_AVAILABLE:
            self.mostrar_notificacion("La librería 'Pillow' es necesaria para ver imágenes.\nInstálala con: pip install Pillow", "error")
            return

        item_id = self.tree_materiales.identify_row(event.y)
        if not item_id:
            return

        item = self.tree_materiales.item(item_id)
        nombre_material = item['values'][1]

        # NOTA: La visualización de imágenes requeriría que el servidor también sirva los archivos de imagen.
        self.mostrar_notificacion("La visualización de imágenes no está implementada para el modo servidor.", "info")

    def configurar_historial_tab(self):
        """
        Configura la interfaz de la pestaña de Historial con campos de entrada separados.
        """
        top_frame = ttk.Frame(self.historial_tab)
        top_frame.pack(fill="x", pady=10, padx=10)

        # Campos para registrar entrada/salida
        frame_inputs = ttk.Frame(top_frame)
        frame_inputs.pack(fill="x")

        ttk.Label(frame_inputs, text="Artículo:").pack(side="left", padx=(0, 5))
        self.articulo_entry_historial = AutocompleteEntry(frame_inputs)
        self.articulo_entry_historial.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.articulo_entry_historial.bind("<<TextChanged>>", self.filtrar_historial_en_tiempo_real)
        self.articulo_entry_historial.bind('<<FocusNext>>', lambda e: self.cantidad_entry.focus_set())
        
        ttk.Label(frame_inputs, text="Cantidad:").pack(side="left", padx=(0, 5))
        self.cantidad_entry = ttk.Entry(frame_inputs)
        self.cantidad_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.cantidad_entry.bind('<Return>', lambda e: self.proveedor_entry.focus_set())

        ttk.Label(frame_inputs, text="Proveedor:").pack(side="left", padx=(0, 5))
        self.proveedor_entry = AutocompleteEntry(frame_inputs)
        # Se establece la lista de autocompletado para el campo de proveedor
        self.proveedor_entry.set_sugerencias(self.nombres_proveedores)
        self.proveedor_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.proveedor_entry.bind('<<FocusNext>>', lambda e: self.destino_entry.focus_set())
        
        ttk.Label(frame_inputs, text="Destino:").pack(side="left", padx=(0, 5))
        self.destino_entry = AutocompleteEntry(frame_inputs)
        self.destino_entry.set_sugerencias(self.nombres_destinos)
        self.destino_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Botones de movimiento
        frame_botones = ttk.Frame(top_frame)
        frame_botones.pack(pady=10)

        ttk.Button(frame_botones, text="Registrar Entrada", command=self.registrar_entrada).pack(side="left", padx=5)
        ttk.Button(frame_botones, text="Registrar Salida", command=self.registrar_salida).pack(side="left", padx=5)
        # Se agrega el nuevo botón para importar historial
        ttk.Button(frame_botones, text="Importar Historial", command=self.importar_historial).pack(side="left", padx=5)
        ttk.Button(frame_botones, text="Exportar Historial", command=self.exportar_historial).pack(side="left", padx=5)
        
        # --- NUEVO BOTÓN PARA ELIMINAR MOVIMIENTOS SELECCIONADOS ---
        ttk.Button(frame_botones, text="Eliminar Selección", command=self.eliminar_movimientos_seleccionados_gui).pack(side="left", padx=5)
        
        # --- NUEVO BOTÓN PARA ELIMINAR TODO EL HISTORIAL ---
        ttk.Button(frame_botones, text="Eliminar Todo el Historial", command=self.eliminar_todo_el_historial).pack(side="left", padx=5)
        ttk.Button(frame_botones, text="Limpiar Filtros", command=self.limpiar_filtros_historial).pack(side="left", padx=5)

        # Treeview para mostrar el historial
        # Frame para contener el Treeview y la Scrollbar
        tree_frame_hist = ttk.Frame(self.historial_tab)
        tree_frame_hist.pack(fill="both", expand=True, padx=10, pady=10)

        # Se elimina la columna de ID y se añade la de unidad
        self.tree_historial = ttk.Treeview(tree_frame_hist, columns=("Artículo", "Tipo", "Cantidad", "Unidad", "Ubicación", "Proveedor", "Fecha"), show="headings")
        self.tree_historial.heading("Artículo", text="Artículo")
        self.tree_historial.heading("Tipo", text="Tipo")
        self.tree_historial.heading("Cantidad", text="Cantidad")
        self.tree_historial.heading("Unidad", text="Unidad")
        self.tree_historial.heading("Ubicación", text="Ubicación")
        self.tree_historial.heading("Proveedor", text="Proveedor")
        self.tree_historial.heading("Fecha", text="Fecha")

        # Configurar colores para las filas de entrada y salida
        self.tree_historial.tag_configure('entrada', background=COLOR_PALETTE["row_entrada"])
        self.tree_historial.tag_configure('salida', background=COLOR_PALETTE["row_salida"])

        self.tree_historial.column("Artículo", stretch=tk.YES)
        self.tree_historial.column("Tipo", width=80, stretch=tk.NO)
        self.tree_historial.column("Cantidad", width=80, stretch=tk.NO)
        self.tree_historial.column("Unidad", width=80, stretch=tk.NO)
        self.tree_historial.column("Ubicación", stretch=tk.YES)
        self.tree_historial.column("Proveedor", stretch=tk.YES)
        self.tree_historial.column("Fecha", stretch=tk.YES)

        scrollbar_hist = ttk.Scrollbar(tree_frame_hist, orient="vertical", command=self.tree_historial.yview)
        self.tree_historial.configure(yscrollcommand=scrollbar_hist.set)
        scrollbar_hist.pack(side="right", fill="y")
        self.tree_historial.pack(side="left", fill="both", expand=True)

        self.mostrar_historial_gui()

        self.menu_contextual_historial = tk.Menu(self.root, tearoff=0)
        # El menú contextual ahora también llama al método de selección múltiple, pero solo para un item.
        # Esto simplifica la lógica y garantiza un comportamiento consistente.
        self.menu_contextual_historial.add_command(label="Editar Movimiento", command=self.editar_movimiento_gui)
        self.menu_contextual_historial.add_command(label="Eliminar Movimiento", command=self.eliminar_movimiento_por_menu)
        # Evento de clic en la cabecera para filtrar
        self.tree_historial.bind("<Button-1>", self.on_historial_header_click)
        self.tree_historial.bind("<Button-3>", self.mostrar_menu_contextual_historial)

    def mostrar_menu_contextual_historial(self, event):
        """
        Muestra el menú contextual al hacer clic derecho en un ítem de la tabla del historial.
        """
        item_id = self.tree_historial.identify_row(event.y)
        if item_id:
            self.tree_historial.selection_set(item_id)
            try:
                self.menu_contextual_historial.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu_contextual_historial.grab_release()

    def eliminar_movimiento_por_menu(self):
        """
        Método que maneja la eliminación de un solo movimiento desde el menú contextual.
        Es una capa delgada que llama al método principal de eliminación múltiple.
        """
        seleccion = self.tree_historial.selection()
        if seleccion:
            self.eliminar_movimientos_seleccionados_gui(seleccion)

    def eliminar_movimientos_seleccionados_gui(self, seleccion=None):
        """
        Elimina uno o más movimientos seleccionados del historial.
        Esta función ahora maneja toda la lógica de confirmación y eliminación.
        """
        if seleccion is None:
            seleccion = self.tree_historial.selection()

        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione al menos un movimiento para eliminar.", "error")
            return
            
        if not messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro de que desea eliminar {len(seleccion)} movimiento(s) seleccionado(s)?"):
            return

        # NOTA: Implementar API DELETE /movimiento/<tipo>/<id> en el servidor
        self.mostrar_notificacion("La eliminación de movimientos no está implementada para el modo servidor.", "info")

    def eliminar_todo_el_historial(self):
        """
        Elimina todos los movimientos de las tablas de entradas y salidas,
        y restablece la cantidad de todos los artículos en el inventario a cero.
        """
        if not messagebox.askyesno("Confirmar Borrado Total",
                                   "ADVERTENCIA: ¿Está seguro de que desea eliminar TODO el historial de movimientos?\n\nEsta acción es irreversible y borrará todos los registros de entradas y salidas.\n\nEl inventario de cada artículo se restablecerá a CERO (0)."):
            return

        # NOTA: Implementar API DELETE /historial/all en el servidor
        self.mostrar_notificacion("La eliminación total del historial no está implementada para el modo servidor.", "info")

    def editar_movimiento_gui(self):
        """
        Abre una ventana de diálogo para editar un movimiento seleccionado del historial.
        """
        seleccion = self.tree_historial.selection()
        if not seleccion:
            self.mostrar_notificacion("Por favor, seleccione un movimiento para editar.", "error")
            return

        item = self.tree_historial.item(seleccion[0])
        valores_actuales = item['values']
        articulo_nombre = valores_actuales[0]
        tipo = valores_actuales[1]
        cantidad_actual = valores_actuales[2]
        ubicacion_actual = valores_actuales[4]

        # NOTA: Implementar API PUT /movimiento/<tipo>/<id> en el servidor
        self.mostrar_notificacion("La edición de movimientos no está implementada para el modo servidor.", "info")

        ventana_edicion = tk.Toplevel(self.root)
        ventana_edicion.title(f"Editar {tipo} de Artículo")
        ventana_edicion.transient(self.root)
        ventana_edicion.grab_set()

        frame_edicion = ttk.Frame(ventana_edicion, padding="10")
        frame_edicion.pack()

        ttk.Label(frame_edicion, text=f"Artículo: {articulo_nombre}").grid(row=0, column=0, columnspan=2, pady=5)

        ttk.Label(frame_edicion, text="Nueva Cantidad:").grid(row=1, column=0, sticky="w", pady=5)
        cantidad_entry = ttk.Entry(frame_edicion)
        cantidad_entry.insert(0, cantidad_actual)
        cantidad_entry.grid(row=1, column=1, pady=5)

        ubicacion_label = "Nueva Ubicación:"
        ttk.Label(frame_edicion, text=ubicacion_label).grid(row=2, column=0, sticky="w", pady=5)
        ubicacion_entry = AutocompleteEntry(frame_edicion)
        ubicacion_entry.set_sugerencias(self.nombres_destinos)
        ubicacion_entry.insert(0, ubicacion_actual)
        ubicacion_entry.grid(row=2, column=1, pady=5)

        def guardar_cambios():
            nueva_cantidad_str = cantidad_entry.get().strip()
            nueva_ubicacion = ubicacion_entry.get().strip().upper()  # Convertir a mayúsculas

            if not nueva_cantidad_str or not nueva_ubicacion:
                self.mostrar_notificacion("Todos los campos son obligatorios.", "error")
                return

            try:
                nueva_cantidad = int(nueva_cantidad_str)
                if nueva_cantidad <= 0:
                    raise ValueError
            except ValueError:
                self.mostrar_notificacion("La nueva cantidad debe ser un número entero positivo.", "error")
                return

            # Aquí iría la llamada a la API del servidor

        ttk.Button(frame_edicion, text="Guardar Cambios", command=guardar_cambios).grid(row=3, column=0, columnspan=2, pady=10)

    def registrar_entrada(self):
        """
        Registra una entrada de artículo en la base de datos y actualiza el inventario.
        Ahora registra el proveedor y el destino.
        """
        nombre = self.articulo_entry_historial.get().strip().upper()  # Convertir a mayúsculas
        cantidad_str = self.cantidad_entry.get().strip()
        proveedor = self.proveedor_entry.get().strip().upper()  # Convertir a mayúsculas
        destino = self.destino_entry.get().strip().upper()  # Convertir a mayúsculas

        if not nombre or not cantidad_str or not proveedor or not destino:
            self.mostrar_notificacion("Los campos Artículo, Cantidad, Proveedor y Destino son obligatorios para una entrada.", "error")
            return

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            self.mostrar_notificacion("La cantidad debe ser un número entero positivo.", "error")
            return

        try:
            payload = {
                "nombre": nombre,
                "cantidad": cantidad,
                "proveedor": proveedor,
                "destino": destino
            }
            response = requests.post(f"{self.server_url}/registrar_entrada", json=payload)
            response.raise_for_status()

            self.mostrar_notificacion(f"Entrada de {cantidad} de '{nombre}' enviada al servidor.", "exito")
            
            # Limpiamos los campos. La GUI se actualizará automáticamente por el evento de WebSocket.
            for entry in [self.articulo_entry_historial, self.cantidad_entry, self.proveedor_entry, self.destino_entry]:
                entry.delete(0, 'end')
            self.articulo_entry_historial.focus_set()

        except requests.exceptions.RequestException as e:
            self.mostrar_notificacion(f"Error al registrar entrada: {e}", "error")

    def registrar_salida(self):
        """
        Registra una salida de artículo en la base de datos y actualiza el inventario.
        """
        nombre = self.articulo_entry_historial.get().strip().upper()  # Convertir a mayúsculas
        cantidad_str = self.cantidad_entry.get().strip()
        destino = self.destino_entry.get().strip().upper()  # Convertir a mayúsculas
        proveedor = self.proveedor_entry.get().strip()

        if not nombre or not cantidad_str or not destino:
            self.mostrar_notificacion("Los campos Artículo, Cantidad y Destino son obligatorios para una salida.", "error")
            return

        if proveedor:
            self.mostrar_notificacion("Para registrar una salida, el campo 'Proveedor' debe estar vacío.", "error")
            return

        try:
            cantidad = int(cantidad_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            self.mostrar_notificacion("La cantidad debe ser un número entero positivo.", "error")
            return

        try:
            payload = {
                "nombre": nombre,
                "cantidad": cantidad,
                "destino": destino
            }
            response = requests.post(f"{self.server_url}/registrar_salida", json=payload)
            
            if response.status_code == 400:
                self.mostrar_notificacion(f"Error del servidor: {response.json().get('message')}", "error")
                return
            response.raise_for_status()

            self.mostrar_notificacion(f"Salida de {cantidad} de '{nombre}' enviada al servidor.", "exito")
            
            for entry in [self.articulo_entry_historial, self.cantidad_entry, self.proveedor_entry, self.destino_entry]:
                entry.delete(0, 'end')
            self.articulo_entry_historial.focus_set()
        except requests.exceptions.RequestException as e:
            self.mostrar_notificacion(f"Error al registrar salida: {e}", "error")

    def importar_historial(self):
        """
        Importa datos de movimientos de inventario desde un archivo Excel.
        ---
        El archivo de Excel debe tener las siguientes columnas:
        'Articulo', 'Tipo', 'Cantidad', 'Ubicacion', 'Proveedor', 'Fecha'
        - El campo 'Tipo' debe ser 'Entrada' o 'Salida'.
        - Para las entradas, se actualizará el stock y se registrará en la tabla 'entradas'.
        - Para las salidas, se restará del stock y se registrará en la tabla 'salidas'.
        - Si el artículo no existe, se creará un nuevo registro en el inventario.
        """
        filepath = filedialog.askopenfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        if not filepath:
            return

        # NOTA: Implementar API POST /historial/importar en el servidor
        self.mostrar_notificacion("La importación de historial no está implementada para el modo servidor.", "info")

    def on_historial_header_click(self, event):
        """
        Maneja el clic en la cabecera de la tabla de historial para mostrar el menú de filtro.
        """
        region = self.tree_historial.identify_region(event.x, event.y)
        if region == "heading":
            column_id = self.tree_historial.identify_column(event.x)
            # El texto de la cabecera puede tener el indicador de filtro '▼'
            column_name = self.tree_historial.heading(column_id, "text").split(' ')[0]
            
            filterable_columns = ["Tipo", "Ubicación", "Proveedor", "Fecha"]
            if column_name in filterable_columns:
                self.mostrar_menu_filtro(event, column_name)

    def mostrar_menu_filtro(self, event, column_name):
        """
        Crea y muestra un menú contextual con opciones de filtro para una columna específica.
        """
        menu = tk.Menu(self.root, tearoff=0)
        
        valores_unicos = []
        # NOTA: Implementar API GET /sugerencias/<columna> en el servidor
        self.mostrar_notificacion("Los filtros de columna no están implementados para el modo servidor.", "info")

        if valores_unicos:
            menu.add_command(label=f"Todos ({column_name})", command=lambda: self.aplicar_filtro_historial(column_name, None))
            menu.add_separator()
            for valor in valores_unicos:
                menu.add_command(label=valor, command=lambda v=valor: self.aplicar_filtro_historial(column_name, v))
        else:
            menu.add_command(label="No hay opciones para filtrar", state="disabled")

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def aplicar_filtro_historial(self, column_name, value):
        """
        Aplica un filtro al diccionario de filtros activos y actualiza la vista.
        """
        if value is None:
            if column_name in self.filtros_activos:
                del self.filtros_activos[column_name]
        else:
            self.filtros_activos[column_name] = value
        self.mostrar_historial_gui()

    def limpiar_filtros_historial(self):
        """
        Limpia todos los filtros activos del historial y refresca la tabla.
        """
        if not self.filtros_activos:
            self.mostrar_notificacion("No hay filtros activos para limpiar.", "info")
            return
        self.filtros_activos.clear()
        self.mostrar_historial_gui()
        self.mostrar_notificacion("Filtros del historial limpiados.", "exito")

    def filtrar_historial_en_tiempo_real(self, event=None):
        """
        Filtra el Treeview del historial en tiempo real basándose en el término de búsqueda del artículo.
        """
        termino_busqueda = self.articulo_entry_historial.get().strip()
        self.mostrar_historial_gui(filtro_articulo=termino_busqueda)

    def mostrar_historial_gui(self, filtro_articulo=None):
        """
        Actualiza y muestra la lista de movimientos en el Treeview del historial.
        Ahora incluye la unidad de medición.
        """
        for item in self.tree_historial.get_children():
            self.tree_historial.delete(item)

        try:
            response = requests.get(f"{self.server_url}/historial")
            response.raise_for_status()
            historial_df = pd.DataFrame(response.json())
            if not historial_df.empty:
                historial_df['fecha'] = pd.to_datetime(historial_df['fecha'])
                historial_df = historial_df.sort_values(by='fecha', ascending=False)

                # --- APLICAR FILTROS ACTIVOS ---
                if self.filtros_activos:
                    df_filtrado = historial_df.copy()
                    for col, val in self.filtros_activos.items():
                        if col == "Tipo":
                            df_filtrado = df_filtrado[df_filtrado['Tipo'].str.lower() == val.lower()]
                        elif col == "Ubicación":
                            df_filtrado = df_filtrado[df_filtrado['Ubicacion'].str.lower() == val.lower()]
                        elif col == "Proveedor":
                            df_filtrado = df_filtrado[df_filtrado['Proveedor'].str.lower() == val.lower()]
                        elif col == "Fecha":  # Filtro "empieza por" para Año-Mes
                            df_filtrado = df_filtrado[df_filtrado['fecha'].dt.strftime('%Y-%m-%d').str.startswith(val)]
                    historial_df = df_filtrado

                # --- APLICAR FILTRO EN TIEMPO REAL (del Entry) ---
                if filtro_articulo:
                    historial_df = historial_df[historial_df['Articulo'].str.contains(filtro_articulo, case=False, na=False)]

                # --- FIN DE FILTROS ---

                # Actualizar cabeceras para mostrar qué filtros están activos
                column_map = {
                    "Artículo": "Artículo", "Tipo": "Tipo", "Cantidad": "Cantidad", 
                    "Unidad": "Unidad", "Ubicación": "Ubicación", "Proveedor": "Proveedor", "Fecha": "Fecha"
                }
                for col_key in column_map:
                    original_text = column_map[col_key]
                    if col_key in self.filtros_activos:
                        # Añade un indicador visual al texto de la cabecera
                        self.tree_historial.heading(col_key, text=f"{original_text} ▼")
                    else:
                        self.tree_historial.heading(col_key, text=original_text)

                historial_df['fecha'] = historial_df['fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
                historial_df.fillna('', inplace=True)

                for _, row in historial_df.iterrows():
                    # Determinar la etiqueta (tag) según el tipo de movimiento para colorear la fila
                    tag = 'entrada' if row['Tipo'] == 'Entrada' else 'salida'
                    self.tree_historial.insert('', 'end', values=list(row), tags=(tag,))

        except Exception as e:
            self.mostrar_notificacion(f"Error al cargar el historial: {e}", "error")

    def exportar_historial(self):
        """Exporta el historial completo a un archivo Excel.
        Ahora incluye la columna de unidad de medición.
        """
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not filepath:
            return

        try:
            response = requests.get(f"{self.server_url}/historial")
            response.raise_for_status()
            historial_df = pd.DataFrame(response.json())
            historial_df.to_excel(filepath, index=False)
            self.mostrar_notificacion(f"Historial exportado a: {filepath}", "exito")

        except Exception as e:
            self.mostrar_notificacion(f"Error al exportar el historial: {e}", "error")

    def mostrar_notificacion(self, mensaje, tipo="info"):
        """
        Muestra una notificación temporal en la esquina inferior derecha.
        """
        frame_bg = {"exito": "#4CAF50", "error": "#F44336", "info": "#2196F3"}
        label_fg = {"exito": "white", "error": "white", "info": "white"}

        notificacion = tk.Toplevel(self.notificacion_frame, bg=frame_bg[tipo])
        notificacion.attributes("-alpha", 0.8)
        notificacion.overrideredirect(True)

        label = tk.Label(notificacion, text=mensaje, bg=frame_bg[tipo], fg=label_fg[tipo], font=("Arial", 10))
        label.pack(padx=10, pady=5)

        notificacion.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width() - notificacion.winfo_width() - 20
        y = self.root.winfo_y() + self.root.winfo_height() - notificacion.winfo_height() - 20
        notificacion.geometry(f'+{x}+{y}')

        self.root.after(3000, notificacion.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    # Manejar el cierre de la ventana para desconectar el cliente de socket
    def on_closing():
        if app.sio.connected:
            app.sio.disconnect()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    app = InventarioApp(root)
    root.mainloop()
