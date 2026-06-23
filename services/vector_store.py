import os
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class VectorStore:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        self.model = SentenceTransformer(model_name, device=device)
        self.index = None
        self.documents = []
        self.dimension = self.model.get_sentence_embedding_dimension()

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Adds documents to the vector store.
        Documents should be a list of dictionaries, each with at least a 'content_raw' key.
        """
        new_contents = [doc['content_raw'] for doc in documents] # Changed from 'content' to 'content_raw'
        new_embeddings = self.model.encode(new_contents, convert_to_numpy=True)

        if self.index is None:
            self.index = faiss.IndexFlatL2(self.dimension)
        
        self.index.add(new_embeddings)
        self.documents.extend(documents)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a semantic search for the query and returns the top-K relevant documents.
        """
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        
        if self.index is None:
            return []

        distances, indices = self.index.search(query_embedding, k)
        
        results = []
        for i, doc_idx in enumerate(indices[0]):
            if doc_idx < len(self.documents): # Ensure index is within bounds
                result_doc = self.documents[doc_idx].copy()
                result_doc['distance'] = distances[0][i]
                results.append(result_doc)
        return results

    def clear(self):
        """Clears the vector store."""
        self.index = None
        self.documents = []
