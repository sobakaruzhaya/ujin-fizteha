import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import PixelSwap from "./reactbits/PixelSwap";
import BlurText from "./reactbits/BlurText";
import "./HomeHero.css";

function HeroPhoto({ reduce }) {
  const image = `${import.meta.env.BASE_URL}images/home-hero-living.webp`;
  const photo = (closeup = false) => (
    <img className={`home-hero-photo${closeup ? " home-hero-photo-closeup" : ""}`} src={image}
      width="1600" height="1402" fetchPriority="high" draggable={false}
      alt="Гостиная с умным термостатом, тёплым светом и деревянной отделкой" />
  );
  return (
    <div className="home-hero-media">
      {reduce ? photo() : <PixelSwap className="home-hero-pixel-swap" aspectRatio="auto"
        firstContent={photo()} secondContent={photo(true)} pattern="pointer"
        pixelSize={36} duration={450} pixelDuration={350} randomness={0.18} bounce={0.2} />}
    </div>
  );
}

export default function HomeHero({ reduce, onDevices }) {
  return (
    <section className="home-hero" aria-labelledby="home-hero-title">
      <HeroPhoto reduce={reduce} />
      <div className="home-hero-content">
        <h1 id="home-hero-title" aria-label="Умный дом UjinFizteha">
          {reduce ? <><span>Умный дом.</span><span className="home-hero-accent">UjinFizteha</span></> : <>
            <BlurText as="span" text="Умный дом." animateBy="words" delay={80} direction="bottom"
              distance={12} blur={7} stepDuration={0.25} />
            <BlurText as="span" text="UjinFizteha" className="home-hero-accent" animateBy="letters"
              delay={28} direction="bottom" distance={12} blur={7} stepDuration={0.25} />
          </>}
        </h1>
        <p className="home-hero-description">Свет, климат и безопасность работают вместе.
          Управляйте устройствами, создавайте сценарии и будьте в курсе того, что происходит дома.</p>
        <div className="home-hero-actions">
          <button className="primary" onClick={onDevices}>Управлять домом <ArrowDownRight size={19} /></button>
          <a className="home-hero-scenarios" href="#scenarios" aria-label="Открыть сценарии">Сценарии <ArrowUpRight size={18} /></a>
        </div>
        <div className="home-hero-bottom"><span>UJIN / HOME</span></div>
      </div>
    </section>
  );
}
