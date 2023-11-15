from config import *

@app.route("/")
def default():
    return render_template('principal.html')

@app.route("/login", methods=['POST', 'GET'])
def login():
    if 'user_id' in session:
        return redirect('/home')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            error_message = 'Todos los campos son obligatorios'
            return render_template('login.html', error=error_message)
        db = firestore.client()
        users_ref = db.collection('users')
        # Obtener la representación cifrada de la contraseña almacenada en la base de datos
        user_query = users_ref.where('username', '==', username).limit(1).get()
        if len(user_query) > 0:
            hashed_password = user_query[0].to_dict()['password']
        else:
            error_message = 'No existe una cuenta con el nombre de usuario especificado'
            return render_template('login.html', error=error_message)
        db.close()
        # Cifrar la contraseña ingresada por el usuario con hashlib
        hashed_password_input = hashlib.sha256(password.encode()).hexdigest()
        # Comparar el hash de la contraseña ingresada por el usuario con el hash de la contraseña almacenada en la base de datos
        if hmac.compare_digest(hashed_password, hashed_password_input):
            session['user_id'] = user_query[0].id
            return redirect('/home')
        else:
            error_message = 'Contraseña incorrecta'
            return render_template('login.html', error=error_message)
    else:
        return render_template('login.html')


@app.route("/logout", methods=["POST"])
def logout():
    # Eliminar el usuario actual de la sesión
    session.pop("user_id", None)
    # Redirigir a la página de inicio de sesión
    return redirect(url_for("login"))

@app.route("/register", methods=['POST', 'GET'])
def register():
    if 'user_id' in session:
        return redirect('/home')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            error_message = 'Todos los campos son obligatorios'
            return render_template('register.html', error=error_message)
        if re.search(r'[<>]', username):
            error_message = 'El nombre de usuario no puede contener caracteres especiales'
            return render_template('register.html', error=error_message)
        if re.search(r'admin', username, re.IGNORECASE):
            error_message = 'El nombre "admin" está reservada para administradores'
            return render_template('register.html', error=error_message)
        if len(username) > 15 and len(username) < 5:
            error_message = 'El nombre de usuario debe tener entre 5 y 15 caracteres'
            return render_template('register.html', error=error_message)
        if len(password) < 8 and len(password) > 30:
            error_message = 'La contraseña debe tener entre 8 y 30 caracteres'
            return render_template('register.html', error=error_message)
        db = firestore.client()
        users_ref = db.collection('users')
        user_exists_query = users_ref.where('username', '==', username).get()
        if len(user_exists_query) > 0:
            error_message = 'Ya existe una cuenta con ese nombre de usuario'
            return render_template('register.html', error=error_message)
        last_user_query = users_ref.order_by(
            'user_id', direction=firestore.Query.DESCENDING).limit(1).get()
        if len(last_user_query) > 0:
            user_id = int(last_user_query[0].to_dict()['user_id']) + 1
        else:
            user_id = 1
        # Cifrar la contraseña con hashlib
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        user_doc = {
            'user_id': str(user_id).zfill(3),
            'username': username,
            'password': hashed_password  # Guardar la representación cifrada de la contraseña
        }
        users_ref.add(user_doc)
        db.close()
        return redirect('/login')
    else:
        return render_template('register.html')

@app.route("/home")
def home():
    if 'user_id' in session:
        # Obtener el usuario conectado desde Firestore
        db = firestore.client()
        users_ref = db.collection('users')
        user_id = session['user_id']
        user_doc = users_ref.document(user_id).get()
        user_data = user_doc.to_dict()
        username = user_data['username']
        db.close()
        # Renderizar la plantilla home.html con el nombre de usuario
        return render_template('home.html', username=username)
    else:
        return redirect('/login')

@app.route("/inventario")
def inventario():
    if 'user_id' in session:
        # Obtener la página actual y la consulta de búsqueda (si se especifica)
        page = request.args.get(get_page_parameter(), type=int, default=1)
        search_query = request.args.get('query', '')
        search_query_upper = search_query.upper()
        # Obtener todos los documentos de la colección "productos" que coinciden con la consulta de búsqueda (si se especifica)
        db = firestore.client()
        productos_ref = db.collection("productos")
        if search_query:
            productos_ref = productos_ref.where('nombre', '>=', search_query_upper).where(
                'nombre', '<=', search_query_upper + '\uf8ff')
        # Obtener los productos como una lista
        productos = [doc.to_dict()
                     for doc in productos_ref.order_by('nombre').get()]
        per_page = 30
        db.close()
        # Obtener los productos para la página actual
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(productos))
        productos_pagina_actual = productos[start_idx:end_idx]
        # Pasar los productos y la paginación a la plantilla como argumentos de función
        return render_template('inventario.html', productos=productos_pagina_actual, search_query=search_query)
    else:
        return redirect('/login')

@app.route("/editar_producto/<producto_id>", methods=['GET'])
def editar_producto(producto_id):
    if 'user_id' in session:
        # Obtener el producto que se va a editar de la base de datos
        db = firestore.client()
        productos_ref = db.collection("productos").where(
            'id_producto', '==', producto_id)
        producto = [doc.to_dict() for doc in productos_ref.stream()]
        db.close()
        # Renderizar la plantilla HTML de edición de productos con los detalles del producto
        return render_template('editar_producto.html', producto=producto)
    else:
        return redirect('/login')

@app.route('/guardar_cambios/<id>', methods=['POST'])
def guardar_cambios(id):
    if 'user_id' in session:
        # Buscar el documento por nombre en Cloud Firestore
        db = firestore.client()
        query = db.collection('productos').where(
            'id_producto', '==', id)
        docs = query.get()
        # Verificar que se encontró un documento
        if len(docs) == 1:
            # Obtener el documento y actualizar los datos
            doc = docs[0]
            doc_ref = db.collection('productos').document(doc.id)
            doc_ref.update({
                'cantidad': int(request.form.get('cantidad')),
                'precio_unitario': float(request.form.get('precio_unitario')),
            })
            db.close()
            # Redirigir a la página de inventario
            return redirect('/inventario')
        else:
            # Si no se encontró ningún documento o se encontró más de uno, mostrar un mensaje de error
            return 'Error: no se pudo encontrar el producto en la base de datos'
    else:
        return redirect('/login')

@app.route('/reportes', methods=['GET'])
def reporte_ventas():
    if 'user_id' in session:
        # Obtener la página actual y la consulta de búsqueda (si se especifica)
        page = request.args.get(get_page_parameter(), type=int, default=1)
        search_query = request.args.get('query', '')
        # Obtener todas las ventas que coinciden con la consulta de búsqueda (si se especifica)
        db = firestore.client()
        ventas_ref = db.collection('ventas')
        if search_query:
            # Buscar el cliente que tenga el dni especificado en search_query
            cliente_ref = db.collection('clientes').where(
                'dni', '==', search_query).limit(1)
            cliente_doc = cliente_ref.get()
            if cliente_doc:
                # Si se encuentra un cliente con ese dni, buscar las ventas correspondientes
                id_cliente = cliente_doc[0].get('id_cliente')
                ventas_ref = ventas_ref.where('id_cliente', '==', id_cliente)
        ventas_dict = {}
        for venta in ventas_ref.stream():
            venta_dict = venta.to_dict()
            venta_id = venta_dict['id_venta']
            if venta_id in ventas_dict:
                ventas_dict[venta_id]['subtotal'] += venta_dict['subtotal']
            else:
                venta_dict['fecha'] = venta_dict['fecha'].replace(
                    tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=-5)))
                # Obtener el nombre del cliente asociado a la venta
                cliente_ref = db.collection('clientes').where(
                    'id_cliente', '==', venta_dict['id_cliente']).limit(1)
                cliente_dict = cliente_ref.get()
                if cliente_dict:
                    cliente_dict = cliente_dict[0].to_dict()
                    venta_dict['dni_cliente'] = cliente_dict['dni']
                else:
                    venta_dict['dni_cliente'] = "Cliente desconocido"
                ventas_dict[venta_id] = venta_dict
        ventas = list(ventas_dict.values())
        per_page = 30
        db.close()
        # Obtener las ventas para la página actual
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(ventas))
        ventas_pagina_actual = ventas[start_idx:end_idx]
        return render_template('reportes.html', ventas=ventas_pagina_actual, query=search_query)
    else:
        return redirect('/login')

@app.route('/ver_factura/<venta_id>', methods=['GET'])
def ver_factura(venta_id):
    if 'user_id' in session:
        db = firestore.client()
        venta_ref = db.collection('ventas').where('id_venta', '==', venta_id)
        venta_docs = venta_ref.get()
        if len(venta_docs) >= 1:
            venta_doc = venta_docs[0]
            # Obtener los datos del cliente correspondiente a la venta
            id_cliente = venta_doc.get('id_cliente')
            cliente_ref = db.collection('clientes').where(
                'id_cliente', '==', id_cliente).limit(1)
            cliente_docs = cliente_ref.get()
            if len(cliente_docs) == 1:
                cliente_doc = cliente_docs[0]
                nombres_cliente = cliente_doc.get('nombres')
                apellidos_cliente = cliente_doc.get('apellidos')
                dni_cliente = cliente_doc.get('dni')
            else:
                # Manejar el caso en el que no se encuentra el cliente
                return 'Cliente no encontrado'
            # Obtener los datos de la venta
            fecha_venta = venta_doc.get('fecha')
            total = venta_doc.get('total')
            # Obtener los datos de los productos de la venta
            productos = []
            for doc in venta_docs:
                producto_venta_data = {}
                # Obtener los detalles del producto correspondiente
                id_producto = doc.get('id_producto')
                producto_ref = db.collection('productos').where(
                    'id_producto', '==', id_producto).limit(1)
                producto_docs = producto_ref.get()
                if len(producto_docs) == 1:
                    producto_doc = producto_docs[0]
                    producto_venta_data['nombre_producto'] = producto_doc.get(
                        'nombre')
                    producto_venta_data['descripcion_producto'] = producto_doc.get(
                        'descripcion')
                else:
                    # Manejar el caso en el que no se encuentra el producto
                    return 'Producto no encontrado'
                # Obtener los datos de la venta
                producto_venta_data['cantidad'] = doc.get('cantidad')
                producto_venta_data['subtotal'] = doc.get('subtotal')
                producto_venta_data['precio_unitario'] = doc.get(
                    'precio_unitario')
                productos.append(producto_venta_data)
            db.close()
            diferencia_tiempo = timedelta(hours=5)
            fecha_hora_utc5 = fecha_venta - diferencia_tiempo
            return render_template('ver_factura.html', venta={
                'nombres_cliente': nombres_cliente,
                'apellidos_cliente': apellidos_cliente,
                'dni_cliente': dni_cliente,
                'fecha_venta': fecha_hora_utc5.strftime('%d/%m/%Y - %H:%M:%S'),
                'id_venta': venta_id,
                'total': total
            }, productos=productos)
        else:
            # Manejar el caso en el que no se encuentra la venta
            return 'Venta no encontrada'
    else:
        return redirect('/login')

@app.route("/facturacion", methods=['GET', 'POST'])
def facturacion():
    if 'user_id' in session:
        productos = []
        # Obtener los productos de la base de datos
        db = firestore.client()
        for producto in db.collection('productos').stream():
            productos.append(producto.to_dict())
        if request.method == 'POST':
            # Obtener los datos del formulario
            id_producto = request.form['producto']
            cantidad = request.form['cantidad']
            if id_producto == "":
                flash('Debe seleccionar un producto.', 'warning')
                return redirect('/facturacion')
            # Validar si el producto está disponible en stock
            producto_stock = db.collection('productos').where('id_producto', '==', id_producto).limit(1).get()
            if producto_stock and int(producto_stock[0].to_dict()['cantidad']) < int(cantidad):
                stock_restante = int(producto_stock[0].to_dict()['cantidad'])
                flash(f'El producto seleccionado solo tiene {stock_restante} unidades disponibles en stock.', 'warning')
                return redirect('/facturacion')
            productos_restantes = db.collection('ventas_borrador').where('id_producto', '==', id_producto).limit(1).get()
            if productos_restantes and int(productos_restantes[0].to_dict()['stock_restante']) < int(cantidad):
                stock_restante = int(productos_restantes[0].to_dict()['stock_restante'])
                flash(f'Restan {stock_restante} unidades del producto.', 'warning')
                return redirect('/facturacion')
            # Verificar si el producto ya está registrado en ventas_borrador
            venta_existente = db.collection('ventas_borrador').where('id_producto', '==', id_producto).limit(1).get()
            for venta in venta_existente:
                venta_dict = venta.to_dict()
                venta_id = venta.id
                venta_dict['cantidad'] = int(cantidad) + int(venta_dict['cantidad'])
                venta_dict['stock_restante'] = int(venta_dict['stock_restante']) - int(cantidad)
                db.collection('ventas_borrador').document(venta_id).update(venta_dict)
                return redirect('/facturacion')
            # Si no se encontró ninguna venta existente, agregar una nueva
            stock_restante = int(producto_stock[0].to_dict()['cantidad'])
            db.collection('ventas_borrador').add({
                'id_producto': id_producto,
                'cantidad': int(cantidad),
                'stock_restante': stock_restante - int(cantidad)
            })
            return redirect('/facturacion')
        ventas = []
        ventas_borrador_ref = db.collection('ventas_borrador')
        for venta in ventas_borrador_ref.stream():
            venta_dict = venta.to_dict()
            id_producto = venta_dict.get('id_producto')
            if id_producto:
                producto_venta = db.collection('productos').where('id_producto', '==', id_producto).limit(1).get()
                for producto in producto_venta:
                    producto_dict = producto.to_dict()
                    venta_dict['nombre'] = producto_dict.get('nombre')
                    venta_dict['precio_unitario'] = producto_dict.get('precio_unitario')
                ventas.append(venta_dict)
        subtotal = 0
        for venta in ventas:
            precio_unitario = venta.get('precio_unitario')
            cantidad = venta.get('cantidad')
            
            if precio_unitario is not None and cantidad is not None:
                venta['precio_unitario'] = float(precio_unitario)
                venta['subtotal'] = float(cantidad) * venta['precio_unitario']
                subtotal += venta['subtotal']
        
        total = subtotal
        db.close()
        return render_template('facturacion.html', ventas=ventas, productos=productos, total=total)
    else:
        return redirect('/login')

@app.route('/facturacion/borrar/<id_producto>', methods=['POST'])
def borrar_producto(id_producto):
    if 'user_id' in session:
        db = firestore.client()
        # Obtener la colección 'ventas' y hacer una consulta por el campo 'id_producto'
        ventas_ref = db.collection('ventas_borrador')
        query = ventas_ref.where('id_producto', '==', id_producto).stream()
        
        # Obtener los documentos que coinciden con la consulta en una lista
        documentos = [doc for doc in query]
        
        # Borrar los documentos de la lista
        for doc in documentos:
            doc.reference.delete()
        db.close()
        return redirect('/facturacion')
    else:
        return redirect('/login')

@app.route('/volver_menu', methods=['POST'])
def volver_home():
    if 'user_id' in session:
        if request.form.get('borrar_borrador') == 'true':
            db = firestore.client()
            # Obtener todas las referencias de documentos en la colección "ventas_borrador"
            borrador_ref = db.collection('ventas_borrador').list_documents()
            # Eliminar cada documento de la colección
            db.close()
            for doc_ref in borrador_ref:
                doc_ref.delete()
        return redirect('/home')
    else:
        return redirect('/login')

@app.route('/confirmar_venta', methods=['POST'])
def confirmar_venta():
    if 'user_id' in session:
        db = firestore.client()
        if request.method == 'POST':
            dni = request.form['dni']
            nombres = request.form['nombres']
            apellidos = request.form['apellidos']
            cliente_ref = db.collection('clientes')
            cliente_query = cliente_ref.where('dni', '==', dni).get()
            if not cliente_query:
                last_user_query = cliente_ref.order_by('id_cliente', direction=firestore.Query.DESCENDING).limit(1).get()
                id_cliente = 1
                if len(last_user_query) > 0:
                    id_cliente = int(last_user_query[0].to_dict()['id_cliente']) + 1
                cliente_doc = {
                    'id_cliente': str(id_cliente).zfill(5),
                    'dni': dni,
                    'nombres': nombres,
                    'apellidos': apellidos
                }
                cliente_ref.add(cliente_doc)
            else:
                id_cliente = cliente_query[0].to_dict()['id_cliente']
        ventas = []
        # Obtener las ventas en borrador de la base de datos
        ventas_borrador_ref = db.collection('ventas_borrador')
        for venta in ventas_borrador_ref.stream():
            venta_dict = venta.to_dict()
            # Obtener el nombre y precio unitario del producto de la venta
            if 'id_producto' in venta_dict:
                producto_venta_query = db.collection('productos').where('id_producto', '==', venta_dict['id_producto']).stream()
                for producto in producto_venta_query:
                    producto_dict = producto.to_dict()
                    venta_dict['nombre'] = producto_dict['nombre']
                    venta_dict['precio_unitario'] = producto_dict['precio_unitario']
            ventas.append(venta_dict)
        # Calcular el subtotal y total de la venta
        subtotal = 0
        for venta in ventas:
            if 'precio_unitario' in venta and 'cantidad' in venta:
                venta['precio_unitario'] = float(venta['precio_unitario'])
                venta['subtotal'] = float(venta['cantidad']) * venta['precio_unitario']
                subtotal += venta['subtotal']
        total = subtotal
        # Obtener el id_venta
        venta_ref = db.collection('ventas')
        last_venta_query = venta_ref.order_by('id_venta', direction=firestore.Query.DESCENDING).limit(1).get()
        id_venta = 1
        if len(last_venta_query) > 0:
            id_venta = int(last_venta_query[0].to_dict()['id_venta']) + 1
        for venta in ventas:
            venta_dict = venta
            if 'id_producto' in venta_dict and 'cantidad' in venta_dict:
                venta_doc = {
                    'id_venta': str(id_venta).zfill(5),
                    'id_producto': venta_dict['id_producto'],
                    'id_cliente': str(id_cliente).zfill(5),
                    'subtotal': venta_dict['cantidad'] * venta_dict['precio_unitario'],
                    'total': total,
                    'cantidad': venta_dict['cantidad'],
                    'precio_unitario': venta_dict['precio_unitario'],
                    'fecha': firestore.SERVER_TIMESTAMP
                }
                venta_ref.add(venta_doc)
        # Actualizar la cantidad de cada producto en la colección "productos"
        for venta in ventas:
            if 'id_producto' in venta and 'cantidad' in venta:
                id_producto = venta['id_producto']
                cantidad_venta = venta['cantidad']
                producto_ref = db.collection('productos').where('id_producto', '==', id_producto).get()
                for producto in producto_ref:
                    producto_dict = producto.to_dict()
                    cantidad_actual = producto_dict['cantidad']
                    cantidad_nueva = cantidad_actual - cantidad_venta
                    producto_doc_ref = db.collection('productos').document(producto.id)
                    producto_doc_ref.update({'cantidad': cantidad_nueva})
        # Eliminar cada documento de la colección "ventas_borrador"
        borrador_docs = ventas_borrador_ref.stream()
        for doc in borrador_docs:
            doc.reference.delete()
        db.close()
        return redirect('/home')
    else:
        return redirect('/login')

if __name__ == '__main__':
    app.run(debug=False)
