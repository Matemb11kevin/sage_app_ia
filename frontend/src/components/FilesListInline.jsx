// src/components/FilesListInline.jsx
import { useEffect } from "react";
import axios from "../services/axiosInstance";

export default function FilesListInline({
  currentUser,
  selectedType,
  selectedMois,
  selectedAnnee,
  files,
  setFiles,
}) {
  // Charger "mes" fichiers selon les filtres
  useEffect(() => {
    async function fetchMine() {
      const params = {
        mine: true,
        type_fichier: selectedType || undefined,
        mois: selectedMois || undefined,
        annee: selectedAnnee || undefined,
      };
      const { data } = await axios.get("/excel-files", { params });
      setFiles(data || []);
    }
    // ne charge que si tout est renseigné
    if (selectedType && selectedMois && selectedAnnee) {
      fetchMine();
    } else {
      setFiles([]); // rien si filtres incomplets
    }
  }, [selectedType, selectedMois, selectedAnnee, setFiles]);

  const isComptable = String(currentUser?.role || "").toLowerCase() === "comptable";

  async function handleDelete(file) {
    const ok = window.confirm(`Supprimer définitivement « ${file.filename} » ?`);
    if (!ok) return;
    try {
      await axios.delete(`/delete-excel/${file.id}`);
      setFiles(prev => prev.filter(f => f.id !== file.id));
    } catch (e) {
      const msg = e?.response?.data?.detail || "Suppression refusée ou erreur serveur.";
      alert(msg);
      // option: recharger la liste si besoin
    }
  }

  return (
    <div className="mt-4">
      <h3 className="text-base font-semibold mb-2">
        Mes fichiers pour {selectedMois || "—"}/{selectedAnnee || "—"} — {selectedType || "—"}
      </h3>

      <table className="w-full border border-gray-300 text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="p-2 border">Nom</th>
            <th className="p-2 border">Type</th>
            <th className="p-2 border">Mois</th>
            <th className="p-2 border">Année</th>
            <th className="p-2 border">Actions</th>
          </tr>
        </thead>
        <tbody>
          {files.map(file => (
            <tr key={file.id}>
              <td className="p-2 border">{file.filename}</td>
              <td className="p-2 border">{file.type_fichier}</td>
              <td className="p-2 border">{file.mois}</td>
              <td className="p-2 border">{file.annee}</td>
              <td className="p-2 border">
                {isComptable && (
                  <button
                    onClick={() => handleDelete(file)}
                    className="px-3 py-1 border rounded hover:bg-gray-100"
                    title="Supprimer ce fichier"
                  >
                    Supprimer
                  </button>
                )}
              </td>
            </tr>
          ))}

          {files.length === 0 && (
            <tr>
              <td className="p-3 border text-gray-500 text-center" colSpan={5}>
                Aucun fichier à afficher pour ces filtres.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
