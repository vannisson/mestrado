import numpy as np

def compute_mse(ref, test):
    try:
        ref_array = np.array(ref, dtype=np.float32)
        test_array = np.array(test, dtype=np.float32)

        if ref_array.shape != test_array.shape:
            min_len = min(len(ref_array), len(test_array))
            ref_array = ref_array[:min_len]
            test_array = test_array[:min_len]

        return np.mean((ref_array - test_array) ** 2)
    except Exception as e:
        print(f"[Metrics] Error computing MSE: {e}")
        return float('inf')


def compute_mae(ref, test):
    try:
        ref_array = np.array(ref, dtype=np.float32)
        test_array = np.array(test, dtype=np.float32)

        if ref_array.shape != test_array.shape:
            min_len = min(len(ref_array), len(test_array))
            ref_array = ref_array[:min_len]
            test_array = test_array[:min_len]

        return np.mean(np.abs(ref_array - test_array))
    except Exception as e:
        print(f"[Metrics] Error computing MAE: {e}")
        return float('inf')


def compute_mape(ref, test, eps=1e-6):
    try:
        ref_array = np.array(ref, dtype=np.float32)
        test_array = np.array(test, dtype=np.float32)

        if ref_array.shape != test_array.shape:
            min_len = min(len(ref_array), len(test_array))
            ref_array = ref_array[:min_len]
            test_array = test_array[:min_len]

        # evita divisão por zero
        ref_array = np.where(ref_array == 0, eps, ref_array)
        return np.mean(np.abs((ref_array - test_array) / ref_array)) * 100
    except Exception as e:
        print(f"[Metrics] Error computing MAPE: {e}")
        return float('inf')


# ==================================================================================
#                               DTW BRUTO (compute_dtw)
# ==================================================================================
# Mantemos sua função original: devolve apenas o custo total acumulado (float).
def compute_dtw(seq1, seq2):
    """
    Calcula a distância DTW “bruta” (soma acumulada dos menores custos) entre duas sequências seq1 e seq2.
    Se seq1/seq2 for lista de escalares (1-D), faz DTW em 1-D (custo = |x - y|).
    Se seq1/seq2 for lista de vetores (2-D), faz DTW multidimensional (custo = ||v1 - v2||).
    Retorna um float com o valor da soma acumulada de menor custo (dtw_mat[n,m]).
    """

    try:
        arr1 = np.array(seq1, dtype=np.float32)
        arr2 = np.array(seq2, dtype=np.float32)

        # ---------------------------------------------
        # Caso 1: ambas 1-D (vetor de escalares)
        # ---------------------------------------------
        if arr1.ndim == 1 and arr2.ndim == 1:
            n, m = len(arr1), len(arr2)
            dtw_mat = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
            dtw_mat[0, 0] = 0.0

            for i in range(1, n + 1):
                for j in range(1, m + 1):
                    cost = abs(arr1[i - 1] - arr2[j - 1])
                    dtw_mat[i, j] = cost + min(
                        dtw_mat[i - 1, j],    # inserção
                        dtw_mat[i, j - 1],    # deleção
                        dtw_mat[i - 1, j - 1] # match diagonal
                    )
            return float(dtw_mat[n, m])

        # ---------------------------------------------
        # Caso 2: ambas 2-D (lista de vetores ou array 2-D)
        # ---------------------------------------------
        elif arr1.ndim == 2 and arr2.ndim == 2:
            n, d1 = arr1.shape
            m, d2 = arr2.shape
            if d1 != d2:
                raise ValueError(f"Dimensionalidade incompatível: seq1 tem dimensão {d1}, seq2 tem {d2}")

            dtw_mat = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
            dtw_mat[0, 0] = 0.0

            for i in range(1, n + 1):
                for j in range(1, m + 1):
                    cost = np.linalg.norm(arr1[i - 1] - arr2[j - 1])
                    dtw_mat[i, j] = cost + min(
                        dtw_mat[i - 1, j],
                        dtw_mat[i, j - 1],
                        dtw_mat[i - 1, j - 1]
                    )
            return float(dtw_mat[n, m])

        else:
            raise ValueError(f"Sequências de forma incompatível: seq1.ndim={arr1.ndim}, seq2.ndim={arr2.ndim}")

    except Exception as e:
        print(f"[Metrics] Error computing DTW: {e}")
        return float("inf")


# ==================================================================================
#                      DTW BRUTO + PATH LENGTH (compute_dtw_and_path_length)
# ==================================================================================
def compute_dtw_and_path_length(seq1, seq2):
    """
    Calcula o DTW “cru” (soma acumulada) E conta quantos passos (i,j) compõem o caminho ótimo.
    Retorna uma tupla: (dtw_total_cost, path_length).

    - seq1, seq2 podem ser listas de escalares (1-D) ou listas de vetores (2-D).
    - path_length é o número de pares (i,j) no caminho de warping de menor custo.
    """

    try:
        arr1 = np.array(seq1, dtype=np.float32)
        arr2 = np.array(seq2, dtype=np.float32)

        # ---------------------------------------------
        # Caso 1: sequência unidimensional (vetor de escalares)
        # ---------------------------------------------
        if arr1.ndim == 1 and arr2.ndim == 1:
            n, m = len(arr1), len(arr2)
            dtw_mat = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
            dtw_mat[0, 0] = 0.0

            for i in range(1, n + 1):
                for j in range(1, m + 1):
                    cost = abs(arr1[i - 1] - arr2[j - 1])
                    dtw_mat[i, j] = cost + min(
                        dtw_mat[i - 1, j],
                        dtw_mat[i, j - 1],
                        dtw_mat[i - 1, j - 1]
                    )

            # Backtracking para contar quantos passos (i,j) foram usados
            i, j = n, m
            path_len = 0
            while i > 0 or j > 0:
                path_len += 1
                escolha = np.argmin((
                    dtw_mat[i - 1, j],    # de cima
                    dtw_mat[i, j - 1],    # da esquerda
                    dtw_mat[i - 1, j - 1] # diagonal
                ))
                if escolha == 0:
                    i -= 1
                elif escolha == 1:
                    j -= 1
                else:
                    i -= 1
                    j -= 1

            return float(dtw_mat[n, m]), path_len

        # ---------------------------------------------
        # Caso 2: sequência bidimensional (lista de vetores)
        # ---------------------------------------------
        elif arr1.ndim == 2 and arr2.ndim == 2:
            n, d1 = arr1.shape
            m, d2 = arr2.shape
            if d1 != d2:
                raise ValueError(f"Dimensões incompatíveis: seq1 tem {d1}, seq2 tem {d2}")

            dtw_mat = np.full((n + 1, m + 1), np.inf, dtype=np.float32)
            dtw_mat[0, 0] = 0.0

            for i in range(1, n + 1):
                for j in range(1, m + 1):
                    cost = np.linalg.norm(arr1[i - 1] - arr2[j - 1])
                    dtw_mat[i, j] = cost + min(
                        dtw_mat[i - 1, j],
                        dtw_mat[i, j - 1],
                        dtw_mat[i - 1, j - 1]
                    )

            # Backtracking para contar passos
            i, j = n, m
            path_len = 0
            while i > 0 or j > 0:
                path_len += 1
                escolha = np.argmin((
                    dtw_mat[i - 1, j],
                    dtw_mat[i, j - 1],
                    dtw_mat[i - 1, j - 1]
                ))
                if escolha == 0:
                    i -= 1
                elif escolha == 1:
                    j -= 1
                else:
                    i -= 1
                    j -= 1

            return float(dtw_mat[n, m]), path_len

        else:
            raise ValueError(f"Sequências com ndim incompatível: {arr1.ndim} vs {arr2.ndim}")

    except Exception as e:
        print(f"[Metrics] Error computing DTW and path: {e}")
        return float("inf"), 0


# ==================================================================================
#                      DTW NORMALIZADO (compute_dtw_normalized)
# ==================================================================================
def compute_dtw_normalized(seq1, seq2):
    """
    Retorna o “DTW médio por passo”:
      dtw_normalized = (custo total de DTW) / (número de passos no caminho).
    Se path_len for zero ou ocorrer erro, retorna inf.
    """
    total_cost, path_len = compute_dtw_and_path_length(seq1, seq2)
    if path_len <= 0:
        return float("inf")
    return total_cost / path_len
