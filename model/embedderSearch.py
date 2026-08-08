import faiss
from sentence_transformers import SentenceTransformer

class SearchEmbedder:

    __name_faiss = None
    __description_faiss = None
    __embedding = None
    __items = 0
    __distance = 0

    def __init__(self, distance=0.7, items=5, model='sentence-transformers/all-MiniLM-L6-v2'):
        self.__name_faiss = faiss.read_index("dataMining/tea_names.index")
        self.__description_faiss = faiss.read_index("dataMining/tea_descriptions.index")
        self.__embedding = SentenceTransformer(model)
        self.__items = items
        self.__distance = distance

    def search_name(self, name: str):
        names_idx = []
        name_embedded = self.__embedding.encode([name], normalize_embeddings=True)

        distances, idx = self.__name_faiss.search(name_embedded, self.__items)

        idx = idx[0].tolist()

        for i, distance in enumerate(distances[0]):
            if distance >= self.__distance:
                names_idx.append(idx[i])

        return names_idx

    def search_description(self, description: str):
        descriptions_idx = []
        description_embedded = self.__embedding.encode([description], normalize_embeddings=True)

        distances, idx = self.__description_faiss.search(description_embedded, self.__items)

        idx = idx[0].tolist()

        for i, distance in enumerate(distances[0]):
            if distance >= self.__distance:
                descriptions_idx.append(idx[i])

        return descriptions_idx

