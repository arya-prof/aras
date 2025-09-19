"""
Knowledge and memory tools for vector search and knowledge base operations.
"""

import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from .base import AsyncTool
from ..models import ToolCategory
from ..config import settings


class MemoryOperationsTool(AsyncTool):
    """Tool for memory operations."""
    
    def __init__(self):
        super().__init__(
            name="memory_operations",
            category=ToolCategory.KNOWLEDGE,
            description="Store, retrieve, and manage memories and knowledge"
        )
        self.chroma_client = None
        self.collection = None
        self._initialize_chroma()
    
    def _initialize_chroma(self):
        """Initialize ChromaDB client."""
        try:
            persist_directory = Path(settings.chroma_persist_directory)
            persist_directory.mkdir(parents=True, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(
                path=str(persist_directory),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Create or get collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="aras_memories",
                metadata={"description": "Aras agent memories and knowledge"}
            )
        except Exception as e:
            print(f"Warning: Failed to initialize ChromaDB: {e}")
            self.chroma_client = None
            self.collection = None
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute memory operation."""
        operation = parameters.get("operation")
        
        if not self.collection:
            raise RuntimeError("ChromaDB not initialized")
        
        if operation == "store_memory":
            return await self._store_memory(
                content=parameters.get("content"),
                metadata=parameters.get("metadata", {}),
                memory_id=parameters.get("memory_id")
            )
        elif operation == "search_memories":
            return await self._search_memories(
                query=parameters.get("query"),
                limit=parameters.get("limit", 10)
            )
        elif operation == "get_memory":
            memory_id = parameters.get("memory_id")
            if not memory_id:
                raise ValueError("memory_id is required for get_memory operation")
            return await self._get_memory(memory_id)
        elif operation == "delete_memory":
            memory_id = parameters.get("memory_id")
            if not memory_id:
                raise ValueError("memory_id is required for delete_memory operation")
            return await self._delete_memory(memory_id)
        elif operation == "list_memories":
            return await self._list_memories(limit=parameters.get("limit", 100))
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _store_memory(self, content: str, metadata: Dict[str, Any], memory_id: Optional[str] = None) -> Dict[str, Any]:
        """Store a memory."""
        if not content:
            raise ValueError("Content is required")
        
        if not memory_id:
            memory_id = f"memory_{len(self.collection.get()['ids'])}"
        
        # Store in ChromaDB
        self.collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[memory_id]
        )
        
        return {
            "success": True,
            "memory_id": memory_id,
            "content": content,
            "metadata": metadata
        }
    
    async def _search_memories(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories."""
        if not query:
            raise ValueError("Query is required")
        
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        memories = []
        for i, doc in enumerate(results['documents'][0]):
            memories.append({
                "memory_id": results['ids'][0][i],
                "content": doc,
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i] if 'distances' in results else None
            })
        
        return memories
    
    async def _get_memory(self, memory_id: str) -> Dict[str, Any]:
        """Get a specific memory."""
        results = self.collection.get(ids=[memory_id])
        
        if not results['documents']:
            raise ValueError(f"Memory {memory_id} not found")
        
        return {
            "memory_id": memory_id,
            "content": results['documents'][0],
            "metadata": results['metadatas'][0]
        }
    
    async def _delete_memory(self, memory_id: str) -> Dict[str, Any]:
        """Delete a memory."""
        self.collection.delete(ids=[memory_id])
        return {"success": True, "memory_id": memory_id}
    
    async def _list_memories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all memories."""
        results = self.collection.get(limit=limit)
        
        memories = []
        for i, doc in enumerate(results['documents']):
            memories.append({
                "memory_id": results['ids'][i],
                "content": doc,
                "metadata": results['metadatas'][i]
            })
        
        return memories
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["store_memory", "search_memories", "get_memory", "delete_memory", "list_memories"],
                    "description": "Memory operation"
                },
                "content": {
                    "type": "string",
                    "description": "Memory content (for store_memory)"
                },
                "metadata": {
                    "type": "object",
                    "description": "Memory metadata (for store_memory)"
                },
                "memory_id": {
                    "type": "string",
                    "description": "Memory ID (for get_memory, delete_memory)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search_memories)"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of results"
                }
            },
            "required": ["operation"]
        }


class VectorSearchTool(AsyncTool):
    """Tool for vector search operations."""
    
    def __init__(self):
        super().__init__(
            name="vector_search",
            category=ToolCategory.KNOWLEDGE,
            description="Perform vector similarity search on knowledge base"
        )
        self.chroma_client = None
        self.collection = None
        self._initialize_chroma()
    
    def _initialize_chroma(self):
        """Initialize ChromaDB client."""
        try:
            persist_directory = Path(settings.chroma_persist_directory)
            persist_directory.mkdir(parents=True, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(
                path=str(persist_directory),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Create or get collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="aras_knowledge",
                metadata={"description": "Aras agent knowledge base"}
            )
        except Exception as e:
            print(f"Warning: Failed to initialize ChromaDB: {e}")
            self.chroma_client = None
            self.collection = None
    
    async def _execute_async(self, parameters: Dict[str, Any]) -> Any:
        """Execute vector search operation."""
        operation = parameters.get("operation")
        
        if not self.collection:
            raise RuntimeError("ChromaDB not initialized")
        
        if operation == "add_documents":
            return await self._add_documents(
                documents=parameters.get("documents", []),
                metadatas=parameters.get("metadatas", []),
                ids=parameters.get("ids", [])
            )
        elif operation == "search":
            return await self._search(
                query=parameters.get("query"),
                limit=parameters.get("limit", 10),
                where=parameters.get("where")
            )
        elif operation == "get_document":
            doc_id = parameters.get("document_id")
            if not doc_id:
                raise ValueError("document_id is required for get_document operation")
            return await self._get_document(doc_id)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> Dict[str, Any]:
        """Add documents to the knowledge base."""
        if not documents:
            raise ValueError("Documents are required")
        
        if not ids:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        if not metadatas:
            metadatas = [{} for _ in documents]
        
        # Ensure all lists have the same length
        min_length = min(len(documents), len(metadatas), len(ids))
        documents = documents[:min_length]
        metadatas = metadatas[:min_length]
        ids = ids[:min_length]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        return {
            "success": True,
            "added_count": len(documents),
            "ids": ids
        }
    
    async def _search(self, query: str, limit: int = 10, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search the knowledge base."""
        if not query:
            raise ValueError("Query is required")
        
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where
        )
        
        documents = []
        for i, doc in enumerate(results['documents'][0]):
            documents.append({
                "document_id": results['ids'][0][i],
                "content": doc,
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i] if 'distances' in results else None
            })
        
        return documents
    
    async def _get_document(self, doc_id: str) -> Dict[str, Any]:
        """Get a specific document."""
        results = self.collection.get(ids=[doc_id])
        
        if not results['documents']:
            raise ValueError(f"Document {doc_id} not found")
        
        return {
            "document_id": doc_id,
            "content": results['documents'][0],
            "metadata": results['metadatas'][0]
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add_documents", "search", "get_document"],
                    "description": "Vector search operation"
                },
                "documents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Documents to add (for add_documents)"
                },
                "metadatas": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Document metadata (for add_documents)"
                },
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Document IDs (for add_documents)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search)"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of results"
                },
                "where": {
                    "type": "object",
                    "description": "Filter conditions (for search)"
                },
                "document_id": {
                    "type": "string",
                    "description": "Document ID (for get_document)"
                }
            },
            "required": ["operation"]
        }
