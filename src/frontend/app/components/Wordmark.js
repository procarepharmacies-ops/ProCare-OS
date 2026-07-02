"use client";

import Image from "next/image";

// The real ProCare logo (public/logo.png, provided by the pharmacy). Used
// everywhere the brand appears: sidebar, login card, and the post-login
// reveal animation.
export default function Wordmark({ size = 38 }) {
  return (
    <Image
      src="/logo.png"
      alt="ProCare"
      width={size}
      height={size}
      style={{ width: size, height: size, borderRadius: "50%" }}
      priority
    />
  );
}
