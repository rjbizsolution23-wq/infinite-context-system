import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from neo4j import GraphDatabase, AsyncGraphDatabase
from openai import AsyncOpenAI

from src.lib.config import SystemConfig, TokenCounter, ContextTier


@dataclass
class Entity:
    """An entity tracked in long-term memory"""
    entity_id: str
    name: str
    entity_type: str  # PERSON, ORG, CONCEPT, EVENT, PREFERENCE, etc.
    attributes: Dict[str, Any] = field(default_factory=dict)
    first_mentioned: datetime = field(default_factory=datetime.now)
    last_mentioned: datetime = field(default_factory=datetime.now)
    mention_count: int = 0
    importance_score: float = 0.5
    
    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "attributes": self.attributes,
            "first_mentioned": self.first_mentioned.isoformat(),
            "last_mentioned": self.last_mentioned.isoformat(),
            "mention_count": self.mention_count,
            "importance_score": self.importance_score
        }


@dataclass
class Relationship:
    """A relationship between two entities"""
    relationship_id: str
    from_entity: str  # entity_id
    to_entity: str    # entity_id
    relationship_type: str  # WORKS_FOR, PREFERS, USES, RELATED_TO, etc.
    strength: float = 0.5  # 0-1
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "relationship_id": self.relationship_id,
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class EntityMemoryGraph:
    """
    Graph-based entity memory system
    
    Tracks:
    - Entities (nodes)
    - Relationships (edges)
    - User preferences
    - Conversation patterns
    """
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: Dict[str, Relationship] = {}
        
        # Index for fast lookup
        self.entity_by_name: Dict[str, str] = {}  # name -> entity_id
        self.relationships_by_entity: Dict[str, List[str]] = defaultdict(list)
    
    def add_entity(self, entity: Entity) -> Entity:
        """Add or update an entity"""
        if entity.entity_id in self.entities:
            # Update existing
            existing = self.entities[entity.entity_id]
            existing.last_mentioned = datetime.now()
            existing.mention_count += 1
            existing.attributes.update(entity.attributes)
            return existing
        else:
            # Add new
            self.entities[entity.entity_id] = entity
            self.entity_by_name[entity.name.lower()] = entity.entity_id
            return entity
    
    def add_relationship(self, relationship: Relationship) -> Relationship:
        """Add or update a relationship"""
        if relationship.relationship_id in self.relationships:
            # Update existing
            existing = self.relationships[relationship.relationship_id]
            existing.strength = (existing.strength + relationship.strength) / 2
            existing.updated_at = datetime.now()
            return existing
        else:
            # Add new
            self.relationships[relationship.relationship_id] = relationship
            self.relationships_by_entity[relationship.from_entity].append(
                relationship.relationship_id
            )
            return relationship
    
    def find_entity(self, name: str) -> Optional[Entity]:
        """Find entity by name"""
        entity_id = self.entity_by_name.get(name.lower())
        return self.entities.get(entity_id) if entity_id else None
    
    def get_entity_relationships(self, entity_id: str,
                                direction: str = "outgoing") -> List[Relationship]:
        """Get all relationships for an entity"""
        if direction == "outgoing":
            rel_ids = self.relationships_by_entity.get(entity_id, [])
            return [self.relationships[rid] for rid in rel_ids]
        elif direction == "incoming":
            return [rel for rel in self.relationships.values() 
                   if rel.to_entity == entity_id]
        else:  # both
            outgoing = self.get_entity_relationships(entity_id, "outgoing")
            incoming = self.get_entity_relationships(entity_id, "incoming")
            return outgoing + incoming
    
    def get_connected_entities(self, entity_id: str, 
                              max_depth: int = 2) -> Set[str]:
        """Get all entities connected within max_depth hops"""
        visited = set()
        queue = [(entity_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            
            visited.add(current_id)
            
            # Get connected entities
            relationships = self.get_entity_relationships(current_id, "both")
            for rel in relationships:
                next_id = rel.to_entity if rel.from_entity == current_id else rel.from_entity
                if next_id not in visited:
                    queue.append((next_id, depth + 1))
        
        return visited
    
    def get_subgraph(self, entity_ids: List[str]) -> Tuple[List[Entity], List[Relationship]]:
        """Get subgraph containing specified entities"""
        entities = [self.entities[eid] for eid in entity_ids if eid in self.entities]
        
        relationships = []
        entity_set = set(entity_ids)
        for rel in self.relationships.values():
            if rel.from_entity in entity_set and rel.to_entity in entity_set:
                relationships.append(rel)
        
        return entities, relationships
    
    def to_dict(self) -> Dict:
        """Export entire graph"""
        return {
            "entities": [e.to_dict() for e in self.entities.values()],
            "relationships": [r.to_dict() for r in self.relationships.values()]
        }


class PersistentMemorySystem:
    """
    Tier 4: Long-term persistent memory with entity tracking
    
    Features:
    - Entity extraction and tracking
    - Relationship graph
    - User preference memory
    - Pattern recognition
    - Cross-session persistence
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.token_counter = TokenCounter(config.primary_llm)
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        
        # Initialize Neo4j Driver
        self.neo4j_driver = None
        if config.neo4j_password:
            try:
                self.neo4j_driver = AsyncGraphDatabase.driver(
                    config.neo4j_uri, 
                    auth=(config.neo4j_user, config.neo4j_password)
                )
            except Exception as e:
                self.logger.error(f"Failed to connect to Neo4j: {e}")
        
        # In-memory fallback
        self.entity_graph = EntityMemoryGraph()
        
        # User preferences
        self.user_preferences: Dict[str, Any] = {}
        
        # Conversation patterns
        self.patterns: List[Dict[str, Any]] = []
        
        # Tracking
        self.total_entities_tracked = 0
        self.total_relationships_tracked = 0

    async def close(self):
        """Close Neo4j connection"""
        if self.neo4j_driver:
            await self.neo4j_driver.close()
    
    async def extract_and_store_entities(self, text: str, 
                                   context: Optional[Dict] = None) -> List[Entity]:
        """
        Extract entities from text using LLM and store in memory
        """
        prompt = f"""
        Extract key entities and their relationships from the following text.
        Return the result in JSON format:
        {{
            "entities": [{{ "name": "...", "type": "...", "importance": 0.0-1.0 }}],
            "relationships": [{{ "from": "...", "to": "...", "type": "..." }}]
        }}
        
        Text: {text}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.summary_model,
                messages=[{"role": "system", "content": "You are an entity extraction expert."},
                         {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response.choices[0].message.content)
            extracted_entities = []
            
            for ent_data in data.get("entities", []):
                entity_id = f"entity_{hash(ent_data['name']) % 1000000}"
                entity = Entity(
                    entity_id=entity_id,
                    name=ent_data['name'],
                    entity_type=ent_data.get('type', 'UNKNOWN'),
                    importance_score=ent_data.get('importance', 0.5),
                    attributes=context or {}
                )
                
                # Store in-memory
                stored = self.entity_graph.add_entity(entity)
                extracted_entities.append(stored)
                
                # Store in Neo4j if available
                await self._store_entity_neo4j(stored)
            
            return extracted_entities
            
        except Exception as e:
            self.logger.error(f"Error in LLM entity extraction: {e}")
            return []

    async def _store_entity_neo4j(self, entity: Entity):
        """Store entity in Neo4j with error handling"""
        if not self.neo4j_driver:
            return
            
        try:
            async with self.neo4j_driver.session() as session:
                await session.run(
                    "MERGE (e:Entity {name: $name}) "
                    "SET e.id = $id, e.type = $type, e.importance = $importance, e.last_mentioned = $last_mentioned",
                    name=entity.name, id=entity.entity_id, type=entity.entity_type,
                    importance=entity.importance_score, last_mentioned=entity.last_mentioned.isoformat()
                )
        except Exception as e:
            self.logger.error(f"Failed to store entity in Neo4j: {e}")
        """
        Extract entities from text and store in memory
        
        In production, use:
        - spaCy NER
        - LLM-based extraction
        - Custom entity recognizers
        """
        # PLACEHOLDER: Simple keyword extraction
        # In production, call LLM with ENTITY_EXTRACTION_PROMPT
        
        entities = []
        
        # Simple heuristic: Look for capitalized words/phrases
        words = text.split()
        potential_entities = []
        
        for i, word in enumerate(words):
            if word[0].isupper() and word.lower() not in ['i', 'the', 'a']:
                # Check if part of multi-word entity
                entity_words = [word]
                j = i + 1
                while j < len(words) and words[j][0].isupper():
                    entity_words.append(words[j])
                    j += 1
                
                potential_entities.append(' '.join(entity_words))
        
        # Create entity objects
        for entity_name in set(potential_entities):
            entity_id = f"entity_{hash(entity_name) % 1000000}"
            
            entity = Entity(
                entity_id=entity_id,
                name=entity_name,
                entity_type="UNKNOWN",  # Would be classified by NER
                attributes=context or {},
                mention_count=1
            )
            
            stored = self.entity_graph.add_entity(entity)
            entities.append(stored)
            self.total_entities_tracked += 1
        
        return entities
    
    def add_user_preference(self, preference_key: str, value: Any,
                           confidence: float = 1.0):
        """Store user preference"""
        self.user_preferences[preference_key] = {
            "value": value,
            "confidence": confidence,
            "updated_at": datetime.now().isoformat()
        }
    
    def get_user_preferences(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve user preferences"""
        if category:
            return {k: v for k, v in self.user_preferences.items() 
                   if k.startswith(f"{category}.")}
        return self.user_preferences
    
    def track_pattern(self, pattern_type: str, pattern_data: Dict[str, Any]):
        """Track conversation patterns"""
        self.patterns.append({
            "type": pattern_type,
            "data": pattern_data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent patterns
        if len(self.patterns) > 100:
            self.patterns = self.patterns[-100:]
    
    def get_entity_context(self, entity_names: List[str],
                          include_relationships: bool = True) -> str:
        """Get context about specific entities"""
        context_parts = []
        
        for name in entity_names:
            entity = self.entity_graph.find_entity(name)
            if not entity:
                continue
            
            # Entity information
            context_parts.append(
                f"\n{entity.name} ({entity.entity_type}):"
            )
            context_parts.append(
                f"  Mentioned {entity.mention_count} times"
            )
            
            if entity.attributes:
                context_parts.append(f"  Attributes: {entity.attributes}")
            
            # Relationships
            if include_relationships:
                relationships = self.entity_graph.get_entity_relationships(
                    entity.entity_id, "outgoing"
                )
                
                if relationships:
                    context_parts.append("  Relationships:")
                    for rel in relationships[:5]:  # Top 5
                        to_entity = self.entity_graph.entities.get(rel.to_entity)
                        if to_entity:
                            context_parts.append(
                                f"    - {rel.relationship_type} {to_entity.name}"
                            )
        
        return '\n'.join(context_parts)
    
    def get_relevant_entities(self, query: str, top_k: int = 10) -> List[Entity]:
        """Find entities relevant to query"""
        # Simple relevance: entity name overlap with query
        query_terms = set(query.lower().split())
        
        scored_entities = []
        for entity in self.entity_graph.entities.values():
            entity_terms = set(entity.name.lower().split())
            overlap = len(query_terms.intersection(entity_terms))
            
            if overlap > 0:
                score = (overlap / len(query_terms)) * entity.importance_score
                scored_entities.append((entity, score))
        
        # Sort by score
        scored_entities.sort(key=lambda x: x[1], reverse=True)
        
        return [entity for entity, score in scored_entities[:top_k]]
    
    def get_context_for_llm(self, query: Optional[str] = None,
                           max_tokens: Optional[int] = None) -> str:
        """Get formatted persistent memory context for LLM"""
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        context_parts = ["=== Long-Term Memory ==="]
        current_tokens = self.token_counter.count('\n'.join(context_parts))
        
        # User preferences
        if self.user_preferences:
            prefs_text = "\n[User Preferences]"
            for key, pref in list(self.user_preferences.items())[:5]:
                prefs_text += f"\n  {key}: {pref['value']}"
            
            prefs_tokens = self.token_counter.count(prefs_text)
            if current_tokens + prefs_tokens <= max_tokens:
                context_parts.append(prefs_text)
                current_tokens += prefs_tokens
        
        # Relevant entities
        if query:
            entities = self.get_relevant_entities(query, top_k=5)
            if entities:
                entity_text = "\n[Relevant Entities]"
                for entity in entities:
                    entity_text += f"\n  {entity.name} ({entity.entity_type})"
                    if entity.attributes:
                        entity_text += f" - {entity.attributes}"
                
                entity_tokens = self.token_counter.count(entity_text)
                if current_tokens + entity_tokens <= max_tokens:
                    context_parts.append(entity_text)
                    current_tokens += entity_tokens
        
        return '\n'.join(context_parts) if len(context_parts) > 1 else ""
    
    def export_memory(self, filepath: str):
        """Export persistent memory to file"""
        export_data = {
            "entity_graph": self.entity_graph.to_dict(),
            "user_preferences": self.user_preferences,
            "patterns": self.patterns,
            "exported_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def import_memory(self, filepath: str):
        """Import persistent memory from file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Restore entities
        for entity_data in data['entity_graph']['entities']:
            entity = Entity(
                entity_id=entity_data['entity_id'],
                name=entity_data['name'],
                entity_type=entity_data['entity_type'],
                attributes=entity_data['attributes'],
                first_mentioned=datetime.fromisoformat(entity_data['first_mentioned']),
                last_mentioned=datetime.fromisoformat(entity_data['last_mentioned']),
                mention_count=entity_data['mention_count'],
                importance_score=entity_data['importance_score']
            )
            self.entity_graph.add_entity(entity)
        
        # Restore relationships
        for rel_data in data['entity_graph']['relationships']:
            rel = Relationship(
                relationship_id=rel_data['relationship_id'],
                from_entity=rel_data['from_entity'],
                to_entity=rel_data['to_entity'],
                relationship_type=rel_data['relationship_type'],
                strength=rel_data['strength'],
                attributes=rel_data['attributes'],
                created_at=datetime.fromisoformat(rel_data['created_at']),
                updated_at=datetime.fromisoformat(rel_data['updated_at'])
            )
            self.entity_graph.add_relationship(rel)
        
        # Restore preferences
        self.user_preferences = data['user_preferences']
        self.patterns = data['patterns']
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about persistent memory"""
        return {
            "total_entities": len(self.entity_graph.entities),
            "total_relationships": len(self.entity_graph.relationships),
            "user_preferences": len(self.user_preferences),
            "tracked_patterns": len(self.patterns),
            "entities_tracked": self.total_entities_tracked,
            "relationships_tracked": self.total_relationships_tracked
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    from config import SystemConfig
    
    print("=" * 70)
    print("TIER 4: PERSISTENT MEMORY - Demo")
    print("=" * 70)
    
    # Initialize
    config = SystemConfig()
    memory = PersistentMemorySystem(config)
    
    # Extract entities from text
    text = "I'm working with John Smith at OpenAI on transformer models."
    entities = memory.extract_and_store_entities(text)
    
    print(f"\nExtracted {len(entities)} entities:")
    for entity in entities:
        print(f"  - {entity.name} ({entity.entity_type})")
    
    # Add user preference
    memory.add_user_preference("ml.preferred_framework", "PyTorch", confidence=0.9)
    memory.add_user_preference("work.role", "ML Engineer")
    
    # Get context
    context = memory.get_context_for_llm(query="transformer models")
    print(f"\nGenerated context:\n{context}")
    
    # Show stats
    print("\nPersistent Memory Statistics:")
    stats = memory.get_stats()
    for key, value in stats.items():
        print(f"  {key:25}: {value}")
    
    print("\n" + "=" * 70)
