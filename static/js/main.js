const toggle=document.getElementById("menuToggle"),nav=document.getElementById("navLinks");
if(toggle&&nav){toggle.addEventListener("click",()=>nav.classList.toggle("open"));nav.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>nav.classList.remove("open")));}
