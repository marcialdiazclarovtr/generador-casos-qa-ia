graph LR
    %% Estilos
    classDef startend fill:#f9f,stroke:#333,stroke-width:2px;
    classDef task fill:#fff,stroke:#333,stroke-width:1px;
    classDef parallel fill:#ffecb3,stroke:#cca000,stroke-width:2px;

    %% Inicio
    Start((Inicio Orden)):::startend --> Venta["Ingresar Venta<br/>(Siebel CRM)"]:::task
    Venta --> Validar["Validar Identidad<br/>(Autentia)"]:::task
    Validar --> Fork1{+}

    %% Rama Paralela de Validaciones
    subgraph Validaciones
        Fork1 --> Plan["Consultar Plan<br/>(Catalogo Siebel)"]:::parallel
        Fork1 --> Score["Evaluación Crediticia<br/>(Equifax)"]:::parallel
        Fork1 --> Recurso["Verificar Recursos<br/>(UIM Inventory)"]:::parallel
        Fork1 --> Factib["Validar Factibilidad<br/>(GIS)"]:::parallel
    end

    %% Reunificación y Proceso Central
    Plan & Score & Recurso & Factib --> Join1{+}
    
    Join1 --> BRM["Crear Cuenta Facturación<br/>(BRM Billing)"]:::task
    BRM --> OSM_COM["Validación y Orquestación<br/>(OSM COM)"]:::task
    OSM_COM --> OSM_SOM["Enviar Info Servicio<br/>(OSM SOM)"]:::task
    OSM_SOM --> UIM_Res["Reservar y Asignar<br/>(UIM)"]:::task
    UIM_Res --> UIM_Conf["Confirmar Recursos<br/>(UIM)"]:::task
    UIM_Conf --> OSM_SOM2["Enviar Info Instalación<br/>(OSM SOM)"]:::task
    OSM_SOM2 --> TOA_Prog["Programar Visita<br/>(TOA Field Service)"]:::task
    TOA_Prog --> TOA_Init["Iniciar Intervención<br/>(TOA)"]:::task
    TOA_Init --> TOA_Prov["Enviar a Aprovisionar<br/>(TOA)"]:::task
    TOA_Prov --> OSM_TOM["Recepcionar y Traducir<br/>(OSM TOM)"]:::task
    OSM_TOM --> GIAP_Sol["Enviar Solicitud<br/>(GIAP)"]:::task
    GIAP_Sol --> GIAP_Aprov["Aprovisionar Servicios<br/>(GIAP)"]:::task
    GIAP_Aprov --> AMS["Configurar Red<br/>(AMS)"]:::task
    AMS --> BBMS["Configurar Perfil<br/>(BBMS)"]:::task
    BBMS --> GIAP_Ent["Entregar Respuesta<br/>(GIAP)"]:::task
    GIAP_Ent --> OSM_TOM2["Recepcionar Respuesta<br/>(OSM TOM)"]:::task
    OSM_TOM2 --> TOA_Desp["Desplegar Respuesta<br/>(TOA)"]:::task
    TOA_Desp --> TOA_Cerrar["Cerrar Orden<br/>(TOA)"]:::task
    
    TOA_Cerrar --> Fork2{+}

    %% Rama Paralela de Cierre
    subgraph Cierre
        Fork2 --> EBS_Act["Registrar Equipos<br/>(EBS Activo Fijo)"]:::task
        
        Fork2 --> EBS_Mat["Declarar Materiales<br/>(NDC)"]:::task
        EBS_Mat --> EBS_Inv["Rebajar Inventario<br/>(EBS Inventory)"]:::task
        
        Fork2 --> OSM_Comp["Indicar Completada<br/>(OSM COM)"]:::task
        OSM_Comp --> Siebel_End["Completar Orden<br/>(Siebel CRM)"]:::task
    end

    %% Fin
    EBS_Act & EBS_Inv & Siebel_End --> End((Orden Completada)):::startend