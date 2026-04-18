class EstadoModel {
  final String semaforo;
  final String interpretacion;
  final List<String> checklist;
  final String conclusion;
  final Map<String, dynamic> datos;
  final Map<String, dynamic> meta;

  EstadoModel({
    required this.semaforo,
    required this.interpretacion,
    required this.checklist,
    required this.conclusion,
    required this.datos,
    required this.meta,
  });

  factory EstadoModel.fromJson(Map<String, dynamic> json) {
    return EstadoModel(
      semaforo: json['semaforo'] ?? 'VERDE',
      interpretacion: json['interpretacion'] ?? '',
      checklist: List<String>.from(json['checklist'] ?? []),
      conclusion: json['conclusion'] ?? '',
      datos: Map<String, dynamic>.from(json['datos'] ?? {}),
      meta: Map<String, dynamic>.from(json['meta'] ?? {}),
    );
  }
}
