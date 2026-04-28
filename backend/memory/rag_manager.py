"""
backend/memory/rag_manager.py

Replaces the dictionary-based memory with a FAISS vector database.
Provides RAG (Retrieval-Augmented Generation) capabilities for the agents.
"""

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict

class RAGManager:
    """
    Manages FAISS index and local embeddings for debate arguments.
    """
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        # Load local embedding model
        self.model = SentenceTransformer(embedding_model)
        self.vector_dim = self.model.get_sentence_embedding_dimension()
        
        # In-memory dictionary mapping session_id to its specific index and documents
        self._sessions = {}

    def _ensure_session(self, debate_id: str):
        """Initialize FAISS index and doc store for a new debate."""
        if debate_id not in self._sessions:
            self._sessions[debate_id] = {
                "index": faiss.IndexFlatL2(self.vector_dim),
                "docs": []  # List of dicts: {id, text, metadata}
            }

    def add_argument(self, debate_id: str, speaker: str, content: str, round_num: int):
        """
        Embed an argument and add it to the FAISS index.
        """
        self._ensure_session(debate_id)
        session = self._sessions[debate_id]
        
        # Create full text representation for embedding
        doc_text = f"[{speaker} in Round {round_num}]: {content}"
        
        # Convert argument into vector space

        embedding = self.model.encode([doc_text], convert_to_numpy=True)
        faiss.normalize_L2(embedding) # Normalize for cosine similarity equivalent
        
        # Add normalized vector to FAISS database
        session["index"].add(embedding)
        
        # Store original text in document mapping
        doc_id = len(session["docs"])
        session["docs"].append({
            "id": doc_id,
            "text": doc_text,
            "speaker": speaker,
            "round_num": round_num,
            "raw_content": content
        })

    def search_similar(self, debate_id: str, query: str, top_k: int = 3, filter_speaker: str = None) -> List[Dict]:
        """
        Search for most similar arguments in the debate.
        """
        if debate_id not in self._sessions:
            return []
            
        session = self._sessions[debate_id]
        if session["index"].ntotal == 0:
            return []
            
        # Embed query
        query_emb = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_emb)
        
        # Perform semantic similarity search in FAISS
        search_k = min(top_k * 3, session["index"].ntotal)
        distances, indices = session["index"].search(query_emb, search_k)
        
        results = []
        for idx in indices[0]:
            if idx == -1:
                continue
            doc = session["docs"][idx]
            
            # Apply basic filtering if requested
            if filter_speaker and doc["speaker"] != filter_speaker:
                continue
                
            results.append(doc)
            if len(results) >= top_k:
                break
                
        return results

    def get_context_for_agent(self, debate_id: str, query: str, speaker: str) -> str:
        """
        Generate a context string for PRO/AGAINST agents using RAG.
        If no specific query is provided, we can retrieve the most recent points.
        """
        if speaker == "USER":
            return ""

        # Retrieve semantically relevant past arguments for context
        results = self.search_similar(debate_id, query, top_k=3)
        
        if not results:
            return ""
            
        lines = []
        lines.append("=== RAG CONTEXT (Relevant Past Arguments) ===")
        lines.append("Use this to maintain consistency and address specific past points:")
        for res in results:
            lines.append(f"- {res['text']}")
        lines.append("==============================================")
        
        return "\n".join(lines)
