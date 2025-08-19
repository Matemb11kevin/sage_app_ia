// src/components/ToastConfig.jsx
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const ToastConfig = () => {
  return (
    <ToastContainer
      position="top-right"
      autoClose={5000}
      newestOnTop
      closeOnClick
      pauseOnHover
      draggable
    />
  );
};

export default ToastConfig;
