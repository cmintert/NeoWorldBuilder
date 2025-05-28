# NeoWorldBuilder - Claude's Understanding

## Project Overview

**NeoWorldBuilder** is a sophisticated worldbuilding tool designed for creative writers, game designers, and storytellers. It uses a graph database approach to organize and interconnect creative ideas, making complex fictional worlds more manageable and explorable.

### Core Philosophy
The application is built around four fundamental concepts:
1. **Names** - Every element starts with a unique identifier
2. **Descriptions** - Rich textual content that brings ideas to life  
3. **Labels** - Categorical classification (Characters, Locations, Events, etc.)
4. **Relations** - Meaningful connections that create narrative coherence

## Architecture Overview

### Technology Stack
- **Frontend**: PyQt6-based desktop application with custom UI components
- **Backend**: Neo4j graph database for data persistence
- **Language**: Python 3.13+ with modern async patterns
- **Packaging**: PyInstaller for distribution (.spec file present)

### Architectural Patterns
- **Service-Oriented Architecture**: Clean separation of concerns with dedicated service classes
- **Worker-Based Threading**: Async database operations using PyQt6 QThread workers
- **Observer Pattern**: Signal/slot communication throughout the UI
- **Configuration Management**: Multi-environment config system with inheritance

## Key Systems

### 1. Database Architecture (`src/core/`)
- **Neo4jModel**: Main database gateway with connection management
- **Worker Classes**: Separate workers for Query, Write, Delete, and Suggestion operations
- **Project Isolation**: All nodes tagged with `_project` property for multi-project support
- **System Properties**: Automatic tracking of `_created`, `_modified`, `_author` metadata
- **Relationship Management**: Bidirectional relationship handling with "stump" node creation

### 2. Configuration System (`src/config/`)
- **Environment-Aware**: Development vs production configuration isolation
- **Hierarchical**: JSON-based configs with inheritance and override capability
- **Security**: Encrypted password storage with auto-generated encryption keys
- **Validation**: Built-in validation for Neo4j names and data structures

### 3. Service Layer (`src/services/`)
Key services include:
- **LLMService**: AI-powered suggestions and content generation
- **NameCacheService**: Performance optimization for autocomplete
- **WorkerManagerService**: Centralized thread/worker lifecycle management
- **AutocompletionService**: Smart name matching and suggestions
- **PropertyService**: Dynamic property management
- **RelationshipTreeService**: Hierarchical relationship visualization

### 4. UI Architecture (`src/ui/`)
- **Controller Pattern**: Centralized business logic in WorldBuildingController
- **Component System**: Reusable UI components with consistent styling
- **Provider Pattern**: Data providers for complex UI interactions
- **Mixin Architecture**: Shared behavior through mixins

## Data Model

### Node Structure
```python
node = {
    "name": str,              # Unique identifier
    "description": str,       # Rich text content
    "tags": List[str],        # User-defined tags
    "labels": List[str],      # Categorical classifications
    "additional_properties": Dict[str, Any],  # Dynamic properties
    "relationships": List[Tuple],  # Connected nodes
    # System properties (auto-managed):
    "_created": ISO timestamp,
    "_modified": ISO timestamp, 
    "_author": str,
    "_project": str
}
```

### Relationship Model
- **Bidirectional**: Relationships can be traversed in both directions
- **Typed**: Each relationship has a semantic type (e.g., "KNOWS", "LOCATED_IN")
- **Property-Rich**: Relationships can carry additional metadata
- **Stump Nodes**: Auto-creation of placeholder nodes for incomplete references

## Technical Patterns

### Error Handling Strategy
- **Structured Logging**: Uses structlog for JSON-formatted, contextual logging
- **Hierarchical Error Handling**: Service-level error handling with UI feedback
- **Graceful Degradation**: Application continues functioning despite non-critical errors
- **User-Friendly Messages**: Technical errors translated to user-understandable language

### Threading and Concurrency
- **Worker Pattern**: Database operations isolated in QThread workers
- **Signal-Slot Communication**: Async result handling through PyQt signals
- **Connection Management**: Automatic connection validation and retry logic
- **Thread Safety**: Database connections properly managed across threads

### Configuration Management
- **Environment Detection**: Automatic dev/prod environment detection
- **File Hierarchy**: Base configs with environment-specific overrides
- **Dynamic Reloading**: Runtime configuration updates with persistence
- **Path Resolution**: Cross-platform path handling for configs and resources

## Development Patterns

### Code Organization
- **Package Structure**: Clear separation by responsibility (core, ui, services, utils)
- **Import Management**: Proper dependency management with circular import prevention
- **Testing Strategy**: Dedicated test files with component-specific testing
- **Documentation**: Comprehensive docstrings with type hints

### Key Design Decisions
1. **Graph Database Choice**: Neo4j chosen for natural relationship modeling
2. **Worker-Based Threading**: Keeps UI responsive during database operations
3. **Project-Based Isolation**: Multi-project support through property-based filtering
4. **Configuration Flexibility**: Environment-aware configs for deployment flexibility
5. **Service Layer**: Business logic separated from UI concerns

## Common Operations

### Node Management
- **CRUD Operations**: Full create, read, update, delete capability
- **Validation**: Name validation and data integrity checks  
- **Relationship Sync**: Automatic relationship consistency maintenance
- **History Tracking**: Modification timestamps and author tracking

### Search and Discovery
- **Autocomplete**: Fast prefix-based name matching
- **Relationship Traversal**: Multi-depth relationship exploration
- **Hierarchical Views**: Label-based organization and browsing
- **Suggestion Engine**: AI-powered content and relationship suggestions

## Extension Points

### Adding New Features
1. **Services**: Add new services in `src/services/` following existing patterns
2. **UI Components**: Create reusable components in `src/ui/components/`
3. **Workers**: Extend worker pattern for new async operations
4. **Configuration**: Add new config sections with validation

### Integration Patterns
- **LLM Integration**: Existing LLMService provides AI capability foundation
- **Export System**: Pluggable export formats (JSON, TXT, CSV, PDF)
- **Style System**: Configurable UI styling through style services
- **Plugin Architecture**: Service-based design naturally supports extensions

## Performance Considerations

### Database Optimization
- **Connection Pooling**: Efficient connection reuse
- **Query Optimization**: Project-scoped queries for performance
- **Relationship Indexing**: Optimized for relationship traversal
- **Name Caching**: In-memory caching for frequent lookups

### UI Responsiveness  
- **Async Operations**: Non-blocking database operations
- **Progressive Loading**: Chunked data loading for large datasets
- **Efficient Updates**: Minimal UI redraws through proper signal handling
- **Memory Management**: Proper cleanup of workers and resources

## Security Model

### Data Protection
- **Encrypted Storage**: Password encryption with generated keys
- **Project Isolation**: Multi-tenant data separation
- **Input Validation**: Comprehensive input sanitization
- **Safe Queries**: Parameterized queries prevent injection

### Access Control
- **Authentication**: Database-level authentication
- **Project Scoping**: All operations scoped to active project
- **Error Information**: Limited error details in production

## Map Component System

The map component is a complex subsystem that allows users to create interactive maps with branching relationships.

### Key Components
- **MapTab**: Main container for map functionality
- **MapViewport**: Handles map display, panning, zooming, and coordinate tracking
- **BaseMapFeatureContainer**: Abstract base class for map feature containers
  - **PinContainer**: Container for pin features (inherits from BaseMapFeatureContainer)
  - **LineContainer**: Container for line features, supports both simple and branching lines (inherits from BaseMapFeatureContainer)
- **DrawingManager**: Manages drawing operations and temporary visualizations
- **FeatureManager**: Coordinates between different features (pins, lines, etc.)

### Interactive Features
- **Pin Placement**: Place pins on maps to mark locations of interest
- **Line Drawing**: Create connections between points with line features
- **Branch Creation**: Create branching lines from existing points/lines
- **Edit Mode**: Modify existing lines and their control points




