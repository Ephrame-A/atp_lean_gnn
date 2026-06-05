from __future__ import annotations

import unittest
import numpy as np
import faiss

from atp_lean_gnn.lemma_index import LemmaIndex


class TestLemmaIndex(unittest.TestCase):
    def test_search_empty_index(self) -> None:
        dim = 8
        index = faiss.IndexFlatL2(dim)
        lemma_ids = []
        lemma_vectors = np.empty((0, dim), dtype=np.float32)

        lemma_index = LemmaIndex(index, lemma_ids, lemma_vectors)
        
        query = np.random.randn(2, dim).astype(np.float32)
        # Search for 5 neighbors, which is more than the index size (0)
        retrieved_ids, retrieved_vecs, scores = lemma_index.search(query, k=5)
        
        self.assertEqual(len(retrieved_ids), 2)
        self.assertEqual(len(retrieved_ids[0]), 5)
        self.assertEqual(retrieved_ids, [[-1] * 5, [-1] * 5])
        self.assertEqual(retrieved_vecs.shape, (2, 5, dim))
        self.assertTrue(np.all(retrieved_vecs == 0.0))

    def test_search_partial_index(self) -> None:
        dim = 8
        index = faiss.IndexFlatL2(dim)
        # Add 2 items
        vectors = np.random.randn(2, dim).astype(np.float32)
        index.add(vectors)
        lemma_ids = [100, 101]
        
        lemma_index = LemmaIndex(index, lemma_ids, vectors)
        
        query = np.random.randn(1, dim).astype(np.float32)
        # Search for 5 neighbors, which is more than the index size (2)
        retrieved_ids, retrieved_vecs, scores = lemma_index.search(query, k=5)
        
        self.assertEqual(len(retrieved_ids), 1)
        self.assertEqual(len(retrieved_ids[0]), 5)
        
        # The first 2 elements should be valid IDs (100 or 101)
        # The remaining 3 elements should be -1
        valid_ids = retrieved_ids[0][:2]
        self.assertTrue(all(x in [100, 101] for x in valid_ids))
        self.assertEqual(retrieved_ids[0][2:], [-1, -1, -1])
        
        self.assertEqual(retrieved_vecs.shape, (1, 5, dim))
        # Check that the invalid indices' vectors are zeroed
        self.assertTrue(np.all(retrieved_vecs[0, 2:] == 0.0))


if __name__ == "__main__":
    unittest.main()
