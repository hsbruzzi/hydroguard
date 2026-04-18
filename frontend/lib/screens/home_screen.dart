import 'package:flutter/material.dart';
import '../models/estado_model.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  late Future<EstadoModel> _future;

  @override
  void initState() {
    super.initState();
    _future = _apiService.fetchEstado();
  }

  void _reload() {
    setState(() {
      _future = _apiService.fetchEstado();
    });
  }

  Color _colorBySemaforo(String semaforo) {
    switch (semaforo.toUpperCase()) {
      case 'ROJO':
        return Colors.red;
      case 'AMARILLO':
        return Colors.amber.shade700;
      default:
        return Colors.green;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('HydroGuard Avellaneda'),
        centerTitle: true,
      ),
      body: FutureBuilder<EstadoModel>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text(
                      'No se pudo cargar el estado actual.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 12),
                    Text('${snapshot.error}', textAlign: TextAlign.center),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: _reload,
                      child: const Text('Reintentar'),
                    ),
                  ],
                ),
              ),
            );
          }

          final estado = snapshot.data!;
          final color = _colorBySemaforo(estado.semaforo);

          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Column(
                    children: [
                      const Text(
                        'ESTADO ACTUAL',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1.2,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        estado.semaforo,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 34,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                _SectionCard(
                  title: 'Interpretación',
                  child: Text(estado.interpretacion, style: const TextStyle(fontSize: 16)),
                ),
                const SizedBox(height: 12),
                _SectionCard(
                  title: 'Checklist operativo',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: estado.checklist
                        .map((item) => Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Text('• $item', style: const TextStyle(fontSize: 16)),
                            ))
                        .toList(),
                  ),
                ),
                const SizedBox(height: 12),
                _SectionCard(
                  title: 'Conclusión',
                  child: Text(
                    estado.conclusion,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
                const SizedBox(height: 12),
                _SectionCard(
                  title: 'Datos técnicos',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Zona: ${estado.meta['zona'] ?? '-'}'),
                      Text('Actualizado: ${estado.meta['updated_at'] ?? '-'}'),
                      const SizedBox(height: 8),
                      Text('Lluvia actual: ${estado.datos['lluvia_actual_mm']} mm'),
                      Text('Lluvia 24 h: ${estado.datos['lluvia_24h_mm']} mm'),
                      Text('Intensidad: ${estado.datos['intensidad_mm_h']} mm/h'),
                      Text('Lluvia 3 días: ${estado.datos['lluvia_3dias_mm']} mm'),
                      Text('Nivel río: ${estado.datos['nivel_rio_m']} m'),
                      Text('Viento: ${estado.datos['direccion_viento']} ${estado.datos['viento_kmh']} km/h'),
                      Text('Alerta SMN: ${estado.datos['alerta_smn']}'),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                ElevatedButton.icon(
                  onPressed: _reload,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Actualizar'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final Widget child;

  const _SectionCard({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            child,
          ],
        ),
      ),
    );
  }
}
