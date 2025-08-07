const teamMembers = [
    {
        name: "Apoorv Karhade",
        role: "Frontend & Database Handler",
        image: "/static/images/apoorv.jpg"
    },
    {
        name: "Krishna Lagad",
        role: "Frontend Developer",
        image: "/static/images/krishna.jpg"
    },
    {
        name: "Swara Deshpande",
        role: "Frontend & Backend Developer",
        image: "/static/images/swara.jpg"
    },
    {
        name: "Pratik Kalburgi",
        role: "Frontend Developer",
        image: "/static/images/pratik.jpg"
    }
];

const container = document.getElementById("team-container");

teamMembers.forEach(member => {
    const div = document.createElement("div");
    div.className = "team-member";
    div.innerHTML = `
        <img src="${member.image}" alt="${member.name}">
        <h2>${member.name}</h2>
        <p>${member.role}</p>
    `;
    container.appendChild(div);
});

